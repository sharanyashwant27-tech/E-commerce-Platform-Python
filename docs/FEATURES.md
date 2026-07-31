# ShopSphere Feature Matrix

Customer journey: see [WORKFLOW.md](./WORKFLOW.md)  
`Login → Browse → Search → Details → Cart → Checkout → Payment → Order → Invoice → Shipping → Delivered → Review`

## Customer Features

| Feature | Status | Where |
|--------|--------|--------|
| User Registration | Done | `/register`, `POST /api/v1/register` |
| Login | Done | `/login`, `POST /api/v1/login` |
| Forgot Password | Done | `/forgot-password`, `/reset-password` |
| Email Verification | Done | `/verify-email`, register emails token |
| Product Search | Done | `/products?q=` |
| Categories | Done | Home + filters + API |
| Filters | Done | Category (web); price/featured (API) |
| Product Details | Done | `/products/{slug}` |
| Wishlist | Done | `/wishlist`, API |
| Shopping Cart | Done | `/cart` |
| Checkout | Done | `/checkout` (address, coupon, COD/Stripe/Razorpay) |
| Coupon Codes | Done | Checkout + `POST /api/v1/coupons/*` |
| Payment Gateway | Done | Stripe / Razorpay sandbox + COD |
| Order Tracking | Done | Order detail + shipping status / tracking # |
| Invoice PDF | Done | `/orders/{id}/invoice` |
| Reviews & Ratings | Done | Product page + API |
| Notifications | Done | In-app + email on status change |
| Order History | Done | `/orders` |
| User Profile | Done | `/account` (profile, addresses, notifications) |

## Seller Features

| Feature | Status | Where |
|--------|--------|--------|
| Seller Registration | Done | Register as seller |
| Product Management | Done | `/seller` create form + API |
| Inventory Management | Done | Seller dashboard + inventory API |
| Pricing | Done | Product create/update prices |
| Discounts | Done | Platform coupons (admin); compare-at price |
| Orders | Done | Seller order list/status API |
| Analytics | Done | `/seller` + `/api/v1/admin/seller/analytics` |
| Sales Reports | Done | 7-day sales on seller dashboard + reports API |
| Product Images | Done | Image URL / `POST /api/v1/uploads/images` |

## Admin Features

| Feature | Status | Where |
|--------|--------|--------|
| Dashboard | Done | `/admin` |
| Users | Done | Admin users tab + API |
| Sellers | Done | Approve/list + API |
| Products | Done | `GET /api/v1/admin/products` |
| Categories | Done | Create + list APIs |
| Orders | Done | Recent orders + status updates |
| Payments | Done | `GET /api/v1/admin/payments` |
| Coupons | Done | Create/list APIs |
| Inventory | Done | `GET /api/v1/admin/inventory` |
| Reports | Done | Sales report API + dashboard |
| Analytics | Done | Revenue, orders, customers, low stock |
| Customer Support | Done | `/support` tickets + admin tab |
