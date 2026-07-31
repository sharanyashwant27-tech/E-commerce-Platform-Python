"""API router aggregation — paths match the public REST contract under /api/v1."""

from fastapi import APIRouter

from api import (
    account,
    admin,
    auth,
    cart,
    categories,
    coupons,
    orders,
    products,
    reviews,
    stores,
    uploads,
    wishlist,
)

api_router = APIRouter()

# Authentication: /register /login /logout /forgot-password /reset-password
api_router.include_router(auth.router)

# Catalog & marketplace stores
api_router.include_router(products.router)
api_router.include_router(categories.router)
api_router.include_router(stores.router)

# Cart: /cart /cart/add /cart/update /cart/remove
api_router.include_router(cart.router)

# Orders: /checkout /orders /orders/{id} /orders/cancel
api_router.include_router(orders.router)

# Reviews: /reviews /reviews/{product_id}
api_router.include_router(reviews.router)

# Coupons: /apply-coupon
api_router.include_router(coupons.router)

# Extended platform APIs
api_router.include_router(account.router, prefix="/account", tags=["Account"])
api_router.include_router(wishlist.router, prefix="/wishlist", tags=["Wishlist"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["Uploads"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin & Seller"])
