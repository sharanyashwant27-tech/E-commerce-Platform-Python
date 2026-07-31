# Application Workflow — User

```
User → Login → Browse Products → Search → Product Details
     → Add to Cart → Checkout → Payment → Order Created
     → Invoice → Shipping → Delivered → Review
```

| Step | Storefront | API |
|------|------------|-----|
| Login | `/login` | `POST /api/v1/login` |
| Browse Products | `/`, `/products` | `GET /api/v1/products` |
| Search | Navbar + `/products?q=` | `GET /api/v1/products?q=` |
| Product Details | `/products/{slug}` | `GET /api/v1/products/{id}` |
| Add to Cart | Form on product page → `/cart` | `POST /api/v1/cart/add` |
| Checkout | `/checkout` | `POST /api/v1/checkout` |
| Payment | COD / Stripe / Razorpay on checkout | Confirm via checkout flow |
| Order Created | Redirect → `/orders/{id}` | Order payload from checkout |
| Invoice | Download PDF on order page | `GET /api/v1/orders/{id}/invoice` |
| Shipping | Status + tracking on order page | Seller/admin status updates |
| Delivered | Order status `delivered` | `PATCH /api/v1/orders/{id}/status` |
| Review | Form on product page (after login) | `POST /api/v1/reviews` |

Demo customer: `customer@shopsphere.local` / `Customer@12345`
