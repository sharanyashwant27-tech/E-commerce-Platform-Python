"""Server-rendered Bootstrap 5 storefront and dashboards."""

from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.deps import get_optional_user
from services.account_service import AccountService
from services.auth_service import AuthService
from services.cart_service import CartService, WishlistService
from services.order_service import OrderService
from services.product_service import ProductService
from config.settings import settings
from auth.security import create_access_token, create_refresh_token
from utils.enums import PaymentProvider, UserRole
from models.entities import Address, Product, SellerProfile, User
from models.session import get_db
from utils.email import send_email
from utils.invoice import build_invoice_pdf

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))
router = APIRouter(include_in_schema=False)


def _ctx(request: Request, user: Optional[User] = None, **extra):
    return {
        "request": request,
        "user": user,
        "app_name": settings.app_name,
        "stripe_pk": settings.stripe_publishable_key,
        **extra,
    }


@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    service = ProductService(db)
    featured, _ = await service.list_products(featured=True, page_size=8)
    latest, _ = await service.list_products(page_size=12)
    categories = await service.list_categories()
    stores = await service.list_stores()
    return templates.TemplateResponse(
        "home.html",
        _ctx(
            request,
            user,
            featured=featured,
            products=latest,
            categories=categories,
            stores=stores,
        ),
    )


@router.get("/products", response_class=HTMLResponse)
async def products_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    q: Optional[str] = None,
    category_id: Optional[int] = None,
    page: int = Query(1, ge=1),
):
    service = ProductService(db)
    products, total = await service.list_products(
        q=q, category_id=category_id, page=page, page_size=12
    )
    categories = await service.list_categories()
    return templates.TemplateResponse(
        "products/list.html",
        _ctx(
            request,
            user,
            products=products,
            categories=categories,
            q=q or "",
            category_id=category_id,
            page=page,
            total=total,
            pages=(total + 11) // 12,
        ),
    )


@router.get("/stores", response_class=HTMLResponse)
async def stores_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    stores = await ProductService(db).list_stores()
    return templates.TemplateResponse(
        "stores/list.html", _ctx(request, user, stores=stores)
    )


@router.get("/stores/{slug}", response_class=HTMLResponse)
async def store_detail(
    slug: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    page: int = Query(1, ge=1),
):
    service = ProductService(db)
    store = await service.get_store_by_slug(slug)
    products, total = await service.list_products(
        seller_id=store.id, page=page, page_size=12
    )
    return templates.TemplateResponse(
        "stores/detail.html",
        _ctx(
            request,
            user,
            store=store,
            products=products,
            page=page,
            total=total,
            pages=(total + 11) // 12,
        ),
    )


@router.get("/products/{slug}", response_class=HTMLResponse)
async def product_detail(
    slug: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    review_error: Optional[str] = None,
    review_ok: Optional[str] = None,
):
    service = ProductService(db)
    product = await service.get_by_slug(slug)
    reviews = await service.list_reviews(product.id)
    return templates.TemplateResponse(
        "products/detail.html",
        _ctx(
            request,
            user,
            product=product,
            reviews=reviews,
            review_error=review_error,
            review_ok=review_ok,
        ),
    )


@router.post("/products/{slug}/review")
async def product_review_submit(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    rating: int = Form(...),
    title: str = Form(""),
    body: str = Form(""),
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    service = ProductService(db)
    product = await service.get_by_slug(slug)
    try:
        await service.add_review(user, product.id, rating, title or None, body or None)
        return RedirectResponse(
            f"/products/{slug}?review_ok=1",
            status_code=303,
        )
    except Exception as exc:
        from urllib.parse import quote

        return RedirectResponse(
            f"/products/{slug}?review_error={quote(str(exc))}",
            status_code=303,
        )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", _ctx(request))


@router.post("/login")
async def login_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    email: str = Form(...),
    password: str = Form(...),
):
    try:
        access, refresh, user = await AuthService(db).authenticate(email, password)
    except Exception:
        return templates.TemplateResponse(
            "auth/login.html",
            _ctx(request, error="Invalid email or password"),
            status_code=400,
        )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("access_token", access, httponly=True, samesite="lax")
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax")
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", _ctx(request))


@router.post("/register")
async def register_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    role: str = Form("customer"),
    store_name: str = Form(""),
):
    try:
        auth = AuthService(db)
        user_role = UserRole(role)
        user = await auth.register(
            email=email,
            password=password,
            full_name=full_name,
            role=user_role,
            store_name=store_name or None,
        )
        token = auth.verification_token(user.email)
        verify_url = f"{settings.base_url}/verify-email?token={token}"
        send_email(
            user.email,
            "Verify your ShopSphere account",
            f'<p>Hi {user.full_name},</p><p><a href="{verify_url}">Verify Email</a></p>',
        )
        access = create_access_token(user.id, user.role.value)
        refresh = create_refresh_token(user.id, user.role.value)
    except Exception as exc:
        return templates.TemplateResponse(
            "auth/register.html",
            _ctx(request, error=str(exc)),
            status_code=400,
        )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie("access_token", access, httponly=True, samesite="lax")
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax")
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@router.get("/cart", response_class=HTMLResponse)
async def cart_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    service = CartService(db)
    cart = await service.get_or_create_cart(user)
    return templates.TemplateResponse(
        "cart/index.html", _ctx(request, user, cart=service.serialize(cart))
    )


@router.post("/cart/add")
async def cart_add(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    variant_id: int = Form(...),
    quantity: int = Form(1),
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    await CartService(db).add_item(user, variant_id, quantity)
    return RedirectResponse("/cart", status_code=303)


@router.get("/checkout", response_class=HTMLResponse)
async def checkout_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    error: Optional[str] = None,
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    service = CartService(db)
    cart = await service.get_or_create_cart(user)
    addresses = await AccountService(db).list_addresses(user)
    return templates.TemplateResponse(
        "cart/checkout.html",
        _ctx(
            request,
            user,
            cart=service.serialize(cart),
            addresses=addresses,
            error=error,
        ),
    )


@router.post("/checkout")
async def checkout_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    address_id: int = Form(...),
    payment_provider: str = Form("cod"),
    coupon_code: str = Form(""),
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    try:
        result = await OrderService(db).checkout(
            user=user,
            address_id=address_id,
            payment_provider=PaymentProvider(payment_provider),
            coupon_code=coupon_code or None,
        )
        order = result["order"]
        if payment_provider != "cod" and result.get("client_secret"):
            # Sandbox: auto-confirm mock Stripe payments
            pid = order.payment.provider_payment_id if order.payment else None
            if pid:
                order = await OrderService(db).confirm_payment(user, order.id, pid)
        await AccountService(db).notify(
            user.id,
            "Order placed",
            f"Order {order.order_number} placed successfully.",
            link=f"/orders/{order.id}",
        )
        return RedirectResponse(f"/orders/{order.id}", status_code=303)
    except Exception as exc:
        service = CartService(db)
        cart = await service.get_or_create_cart(user)
        addresses = await AccountService(db).list_addresses(user)
        return templates.TemplateResponse(
            "cart/checkout.html",
            _ctx(
                request,
                user,
                cart=service.serialize(cart),
                addresses=addresses,
                error=str(exc),
            ),
            status_code=400,
        )


@router.get("/orders", response_class=HTMLResponse)
async def orders_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    orders, _ = await OrderService(db).list_orders(user)
    return templates.TemplateResponse(
        "orders/list.html", _ctx(request, user, orders=orders)
    )


@router.get("/orders/{order_id}", response_class=HTMLResponse)
async def order_detail(
    order_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    order = await OrderService(db).get_order(order_id, user)
    visible_items = list(order.items)
    seller_profile = None
    if user.role == UserRole.SELLER:
        seller_profile = (
            await db.execute(select(SellerProfile).where(SellerProfile.user_id == user.id))
        ).scalar_one_or_none()
        if seller_profile:
            visible_items = [i for i in order.items if i.seller_id == seller_profile.id]
    return templates.TemplateResponse(
        "orders/detail.html",
        _ctx(
            request,
            user,
            order=order,
            visible_items=visible_items,
            seller_view=bool(seller_profile),
        ),
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    if not user or user.role != UserRole.ADMIN:
        return RedirectResponse("/login", status_code=303)
    import json

    analytics = await OrderService(db).admin_analytics()
    users = (await db.execute(select(User).order_by(User.created_at.desc()).limit(20))).scalars().all()
    sellers = (
        await db.execute(select(SellerProfile).options(selectinload(SellerProfile.user)))
    ).scalars().all()
    tickets = await AccountService(db).list_tickets(user, all_tickets=True)
    chart_labels = [d["date"] for d in analytics.get("sales_by_day", [])]
    chart_orders = [d["orders"] for d in analytics.get("sales_by_day", [])]
    chart_revenue = [d["revenue"] for d in analytics.get("sales_by_day", [])]
    return templates.TemplateResponse(
        "admin/dashboard.html",
        _ctx(
            request,
            user,
            analytics=analytics,
            users=users,
            sellers=sellers,
            tickets=tickets[:20],
            chart_labels_json=json.dumps(chart_labels),
            chart_orders_json=json.dumps(chart_orders),
            chart_revenue_json=json.dumps(chart_revenue),
        ),
    )


@router.post("/admin/sellers/{seller_id}/approve")
async def admin_approve_seller_web(
    seller_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    if not user or user.role != UserRole.ADMIN:
        return RedirectResponse("/login", status_code=303)
    seller = await db.get(SellerProfile, seller_id)
    if seller:
        seller.is_approved = True
        await db.flush()
    return RedirectResponse("/admin", status_code=303)


@router.get("/seller", response_class=HTMLResponse)
async def seller_dashboard(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    if not user or user.role not in (UserRole.SELLER, UserRole.ADMIN):
        return RedirectResponse("/login", status_code=303)
    analytics = await OrderService(db).seller_analytics(user)
    seller = (
        await db.execute(select(SellerProfile).where(SellerProfile.user_id == user.id))
    ).scalar_one_or_none()
    seller_products = []
    seller_orders = []
    if seller:
        result = await db.execute(
            select(Product)
            .options(selectinload(Product.variants), selectinload(Product.images))
            .where(Product.seller_id == seller.id)
        )
        seller_products = result.scalars().all()
        seller_orders, _ = await OrderService(db).list_orders(user, page=1, page_size=20)
    categories = await ProductService(db).list_categories()
    return templates.TemplateResponse(
        "seller/dashboard.html",
        _ctx(
            request,
            user,
            analytics=analytics,
            products=seller_products,
            categories=categories,
            seller=seller,
            seller_orders=seller_orders,
        ),
    )


@router.post("/seller/products")
async def seller_create_product(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    name: str = Form(...),
    description: str = Form(...),
    category_id: int = Form(...),
    base_price: float = Form(...),
    stock: int = Form(10),
    brand: str = Form(""),
    image_url: str = Form(""),
):
    if not user or user.role not in (UserRole.SELLER, UserRole.ADMIN):
        return RedirectResponse("/login", status_code=303)
    await ProductService(db).create_product(
        user,
        {
            "name": name,
            "description": description,
            "category_id": category_id,
            "base_price": base_price,
            "brand": brand or None,
            "image_urls": [image_url] if image_url else [],
            "variants": [
                {
                    "sku": f"SKU-{name[:8].upper().replace(' ', '')}",
                    "name": "Default",
                    "price": base_price,
                    "stock": stock,
                }
            ],
        },
    )
    return RedirectResponse("/seller", status_code=303)


@router.get("/account", response_class=HTMLResponse)
async def account_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    addresses = await AccountService(db).list_addresses(user)
    notes = await AccountService(db).list_notifications(user)
    return templates.TemplateResponse(
        "account/profile.html",
        _ctx(request, user, addresses=addresses, notifications=notes),
    )


@router.post("/account/address")
async def account_add_address(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    full_name: str = Form(...),
    phone: str = Form(...),
    line1: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    postal_code: str = Form(...),
    label: str = Form("Home"),
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    await AccountService(db).create_address(
        user,
        {
            "label": label,
            "full_name": full_name,
            "phone": phone,
            "line1": line1,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": "India",
            "is_default": True,
        },
    )
    return RedirectResponse("/account", status_code=303)


@router.get("/wishlist", response_class=HTMLResponse)
async def wishlist_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    items = await WishlistService(db).list_items(user)
    return templates.TemplateResponse(
        "account/wishlist.html", _ctx(request, user, items=items)
    )


@router.post("/wishlist/add")
async def wishlist_add(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    product_id: int = Form(...),
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    try:
        await WishlistService(db).add(user, product_id)
    except Exception:
        pass
    return RedirectResponse("/wishlist", status_code=303)


@router.get("/support", response_class=HTMLResponse)
async def support_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    tickets = await AccountService(db).list_tickets(
        user, all_tickets=(user.role == UserRole.ADMIN)
    )
    return templates.TemplateResponse(
        "account/support.html", _ctx(request, user, tickets=tickets)
    )


@router.post("/support")
async def support_submit(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
    subject: str = Form(...),
    message: str = Form(...),
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    await AccountService(db).create_ticket(user, subject, message, None)
    return RedirectResponse("/support", status_code=303)


@router.get("/orders/{order_id}/invoice")
async def order_invoice(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[Optional[User], Depends(get_optional_user)],
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    order = await OrderService(db).get_order(order_id, user)
    pdf = build_invoice_pdf(order)
    filename = f"{order.invoice_number or order.order_number}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("auth/forgot_password.html", _ctx(request))


@router.post("/forgot-password")
async def forgot_password_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    email: str = Form(...),
):
    auth = AuthService(db)
    user = await auth.get_by_email(email)
    if user:
        token = auth.reset_token(user.email)
        reset_url = f"{settings.base_url}/reset-password?token={token}"
        send_email(
            user.email,
            "Reset your ShopSphere password",
            f'<p><a href="{reset_url}">Reset Password</a></p>',
        )
    return templates.TemplateResponse(
        "auth/message.html",
        _ctx(
            request,
            message="If the email exists, a reset link has been sent.",
            ok=True,
            title="Password reset",
        ),
    )


@router.get("/verify-email", response_class=HTMLResponse)
async def verify_email_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    token: str = "",
):
    message = "Invalid token"
    ok = False
    if token:
        try:
            await AuthService(db).verify_email(token)
            message = "Email verified successfully. You can log in."
            ok = True
        except Exception as exc:
            message = str(exc)
    return templates.TemplateResponse(
        "auth/message.html", _ctx(request, message=message, ok=ok, title="Email Verification")
    )


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = ""):
    return templates.TemplateResponse(
        "auth/reset_password.html", _ctx(request, token=token)
    )


@router.post("/reset-password")
async def reset_password_submit(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    token: str = Form(...),
    new_password: str = Form(...),
):
    try:
        await AuthService(db).reset_password(token, new_password)
        return templates.TemplateResponse(
            "auth/message.html",
            _ctx(request, message="Password updated. Please log in.", ok=True, title="Password reset"),
        )
    except Exception as exc:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            _ctx(request, token=token, error=str(exc)),
            status_code=400,
        )
