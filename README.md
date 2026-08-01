# ShopSphere — E-commerce Platform (Python / FastAPI)

Production-ready Amazon/Flipkart-style marketplace built with **Clean Architecture**, **SOLID** principles, **FastAPI**, **SQLAlchemy**, **JWT/OAuth2**, **Jinja2 + Bootstrap 5**, **Redis**, **Celery**, and **Stripe/Razorpay** sandbox payments.

**Preferred URL:** [http://127.0.0.1:8908](http://127.0.0.1:8908)  
(`http://localhost:8908` redirects HTML only — CSS/JS stay same-origin so styles apply.)  
**API docs (Swagger):** [http://127.0.0.1:8908/docs](http://127.0.0.1:8908/docs)  
**ReDoc:** [http://127.0.0.1:8908/redoc](http://127.0.0.1:8908/redoc)

> Prefer **127.0.0.1** on Windows/Docker. Redirecting stylesheets from `localhost` → `127.0.0.1` is treated as cross-origin by browsers and can leave the site unstyled. Product photos are local under `/static/images/` (no runtime CDN).

## Stack

| Layer | Technology |
|--------|------------|
| Runtime | Python 3.13 (compatible with 3.12+) |
| API | FastAPI + OpenAPI/Swagger |
| ORM | SQLAlchemy 2.x (async) |
| DB | PostgreSQL (prod) / SQLite (dev) |
| Migrations | Alembic |
| Auth | JWT + OAuth2 password flow, RBAC (Admin / Seller / Customer) |
| UI | Jinja2 templates + Bootstrap 5 |
| Cache / Jobs | Redis + Celery |
| Payments | Stripe & Razorpay sandbox (mock fallback without real keys) |
| Tests | Pytest + pytest-cov (≥85%) |
| Deploy | Docker Compose + GitHub Actions CI |

## Features

- Product catalog: categories, variants, inventory, images
- Image-based product search (upload a photo via nav camera or `POST /api/v1/products/search-by-image`)
- Real-time inventory sync (Redis pub/sub + SSE) on product, seller, and admin pages
- Multi-seller marketplace: storefronts, sold-by attribution, cart grouped by seller, admin approve/suspend
- Shopping cart & wishlist
- Checkout with tax, shipping rules, coupons/discount engine
- Orders, invoices, shipping status, order history
- Reviews & ratings
- Admin analytics dashboard (sales, orders, revenue, inventory)
- Seller dashboard (catalog, inventory, sales)
- Email verification, password reset, SMTP notifications
- Structured logging, centralized exceptions, env-based config

## Project structure

```
api/ auth/ models/ schemas/ services/ repository/
templates/ static/ uploads/ middleware/ utils/ config/
migrations/ app/workers/ tests/ docs/
main.py  requirements.txt  Dockerfile  docker-compose.yml
```

Full tree: `docs/STRUCTURE.md`.

## Quick start (local, port 8908)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # or use the provided .env

python scripts/seed.py
python -m uvicorn main:app --host 0.0.0.0 --port 8908 --reload
```

Open **http://127.0.0.1:8908** (preferred on Windows/Docker).

### Demo accounts

| Role | Email | Password |
|------|--------|----------|
| Admin | `admin@shopsphere.local` | `Admin@12345` |
| Seller (Asha Electronics) | `seller@shopsphere.local` | `Seller@12345` |
| Seller (CraftHaus Fashion) | `seller2@shopsphere.local` | `Seller@12345` |
| Seller (HomeNest Living) | `seller3@shopsphere.local` | `Seller@12345` |
| Customer | `customer@shopsphere.local` | `Customer@12345` |

Coupon: `WELCOME10` (10% off, min ₹500)  
Stores: `/stores`, `/stores/asha-electronics`, `/stores/crafthaus-fashion`, `/stores/homenest-living`

## Docker

Repository: [sharanyashwant27-tech/E-commerce-Platform-Python](https://github.com/sharanyashwant27-tech/E-commerce-Platform-Python)

The image is built from [`Dockerfile`](./Dockerfile). **`README.md` is baked into the image** at `/app/README.md` (also linked from the image OCI documentation label). Product photos live under `/app/static/images/` so the storefront does not need Unsplash/CDN at runtime.

### Build the image

```bash
docker build -t shopsphere:latest .

# Confirm README is inside the image
docker run --rm shopsphere:latest cat /app/README.md | more
```

### Run the app container (SQLite-friendly quick start)

```bash
docker run --rm -p 127.0.0.1:8908:8908 \
  -e SECRET_KEY=change-me-in-production \
  -e BASE_URL=http://127.0.0.1:8908 \
  shopsphere:latest
```

Open **http://127.0.0.1:8908**. Seed data after first boot if needed:

```bash
docker exec -it <container_id> python scripts/seed.py
```

### Docker Compose (recommended)

```bash
docker compose up --build
```

Services: `web` (`127.0.0.1:8908`), `worker` (Celery), `db` (Postgres, internal), `redis` (internal).

Compose runs migrations and `scripts/seed.py` on web startup. Demo accounts are listed above.

Read the in-container docs anytime:

```bash
docker compose exec web cat /app/README.md
```

## Alembic

```bash
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

On first local run, `create_all` also creates tables automatically for SQLite.

## API overview

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/register` | Register customer/seller |
| POST | `/api/v1/login` | OAuth2 password login |
| POST | `/api/v1/logout` | Logout |
| POST | `/api/v1/forgot-password` | Request password reset |
| POST | `/api/v1/reset-password` | Reset password |
| GET/POST/PUT/DELETE | `/api/v1/products` | Catalog CRUD |
| GET/POST/PUT/DELETE | `/api/v1/categories` | Category CRUD |
| GET | `/api/v1/cart` | Get cart |
| POST/PUT/DELETE | `/api/v1/cart/add|update|remove` | Cart mutations |
| POST | `/api/v1/checkout` | Checkout + payment intent |
| GET | `/api/v1/orders` | Order history |
| PUT | `/api/v1/orders/cancel` | Cancel order |
| POST/GET | `/api/v1/reviews` | Create / list reviews |
| POST | `/api/v1/apply-coupon` | Validate coupon |

See `docs/API.md` and interactive docs at `/docs`.

## Payments (sandbox)

Without real API keys, the gateway returns **mock** Stripe `client_secret` / Razorpay `order_id` values so checkout can be tested end-to-end. Set real keys in `.env` to hit live sandbox APIs.

Supported `payment_provider` values: `stripe`, `razorpay`, `cod`.

## Tests

```bash
pytest
```

Coverage gate is **85%** (`pytest.ini`).

## Celery (optional locally)

Requires Redis:

```bash
celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

If Redis is down, the app still runs; email falls back to logging, and cache is skipped.

## Configuration

See `.env.example` for all variables (`SECRET_KEY`, `DATABASE_URL`, SMTP, Stripe, Razorpay, Redis, etc.).

## License

MIT — use freely for learning and production adaptations.
