# ShopSphere REST API

Base URL: `http://localhost:8908/api/v1`  
Swagger: `http://localhost:8908/docs`

## Authentication

| Method | Path | Description |
|--------|------|-------------|
| POST | `/register` | Register customer/seller |
| POST | `/login` | OAuth2 password login |
| POST | `/logout` | Logout (clear session cookies) |
| POST | `/forgot-password` | Send reset email |
| POST | `/reset-password` | Set new password with token |

## Products

| Method | Path | Description |
|--------|------|-------------|
| GET | `/products` | List/search products |
| POST | `/products/search-by-image` | Visual search — multipart `file` image; returns ranked `items` with `match_score` |
| GET | `/products/{id}` | Product details |
| POST | `/products` | Create product (seller) |
| PUT | `/products/{id}` | Update product (seller) |
| DELETE | `/products/{id}` | Soft-delete product (seller) |
| PATCH | `/products/variants/{variant_id}/inventory` | Set absolute stock (seller/admin) |

## Inventory (real-time sync)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/inventory/health` | Sync probe + channel metadata |
| GET | `/inventory/variants/{variant_id}` | Current stock snapshot |
| GET | `/inventory/products/{product_id}` | All active variant stock for a product |
| GET | `/inventory/stream` | SSE stream (`event: inventory`) — optional `variant_id` / `product_id` filters |

Stock changes from checkout, cancel, and inventory PATCH publish on Redis channel `shopsphere:inventory` (with an in-process fallback for local/dev).

## Marketplace stores

| Method | Path | Description |
|--------|------|-------------|
| GET | `/stores` | List approved seller storefronts |
| GET | `/stores/{slug}` | Store profile + paginated products |

Cart responses include `seller_groups` (items grouped by store). Sellers only see/cancel/ship orders that are sole-seller; multi-seller orders are customer/admin managed. Admin: `POST /admin/sellers/{id}/approve` and `POST /admin/sellers/{id}/suspend`.

## Categories

| Method | Path | Description |
|--------|------|-------------|
| GET | `/categories` | List categories |
| POST | `/categories` | Create (admin) |
| PUT | `/categories/{id}` | Update (admin) |
| DELETE | `/categories/{id}` | Soft-delete (admin) |

## Cart

| Method | Path | Description |
|--------|------|-------------|
| GET | `/cart` | Get cart |
| POST | `/cart/add` | Add item `{variant_id, quantity}` |
| PUT | `/cart/update` | Update item `{item_id, quantity}` |
| DELETE | `/cart/remove` | Remove item `{item_id}` |

## Orders

| Method | Path | Description |
|--------|------|-------------|
| POST | `/checkout` | Place order |
| GET | `/orders` | Order history |
| GET | `/orders/{id}` | Order detail |
| PUT | `/orders/cancel` | Cancel order `{order_id}` |

## Reviews

| Method | Path | Description |
|--------|------|-------------|
| POST | `/reviews` | Create review `{product_id, rating, comment}` |
| GET | `/reviews/{product_id}` | List product reviews |

## Coupons

| Method | Path | Description |
|--------|------|-------------|
| POST | `/apply-coupon` | Validate/apply `{code, order_amount}` |

Send `Authorization: Bearer <access_token>` on protected routes.
