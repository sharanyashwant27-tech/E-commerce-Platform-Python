# Folder Structure

```
ecommerce-platform/
├── app/                  # App package + Celery workers
│   └── workers/
├── api/                  # REST routers + Jinja web routes (web.py)
├── auth/                 # JWT/OAuth2 security + FastAPI deps
├── models/               # SQLAlchemy entities + DB session
├── schemas/              # Pydantic request/response models
├── services/             # Business logic / use cases
├── repository/           # Data-access layer
├── templates/            # Jinja2 HTML templates
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── uploads/              # Local product images & invoices
├── middleware/           # Exception handlers
├── utils/                # Enums, logging, email, payments, cache, invoice PDF
├── config/               # Settings / env configuration
├── migrations/           # Alembic migrations
├── tests/
├── docs/
├── scripts/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
└── main.py               # Uvicorn entrypoint
```

## Run

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8908
```
