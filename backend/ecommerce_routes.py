"""Rotas FastAPI completas do E-Commerce Gráfico, RBAC, Checkout, Produção e Admin."""

from __future__ import annotations

import copy
import csv
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import openpyxl
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth_rbac import (
    EDITOR_PROFILE_BASIC,
    EDITOR_TOOL_LABELS,
    RBAC_MODULES,
    AuthContext,
    check_rate_limit,
    create_access_token,
    create_notification_once,
    enforce_editor_tool_permissions,
    ensure_owner_or_staff,
    get_current_auth,
    get_optional_auth,
    hash_password,
    log_audit,
    normalize_editor_tools,
    require_permission,
    resolve_user_permissions,
    verify_password,
    verify_webhook_signature,
)
from backend.calendar_engine import generate_agenda_pages
from backend.database import BASE_DIR, SessionLocal, get_db
from backend.models import (
    ArtworkApproval,
    AuditLog,
    Cart,
    CartItem,
    Category,
    Coupon,
    CustomerAddress,
    Favorite,
    GraphicTemplate,
    GraphicTemplateVersion,
    MediaFile,
    Notification,
    Order,
    OrderItem,
    OrderStatusHistory,
    PaymentTransaction,
    Product,
    ProductVariation,
    Project,
    ProjectVersion,
    Role,
    StoreSetting,
    SupportTicket,
    User,
)
from backend.pdf_engine import export_project_bundle, render_pages_to_pdf_bytes
from backend.preflight_engine import run_preflight
from backend.pricing_engine import (
    calculate_item_price,
    calculate_shipping,
    validate_and_apply_coupon,
)
from backend.schemas import ProjectConfig, default_project_config

PRIVATE_STORAGE_DIR = BASE_DIR / "storage_private"
PUBLIC_UPLOADS_DIR = BASE_DIR / "uploads"

ORDER_STATUS_LABELS: dict[str, str] = {
    "aguardando_pagamento": "Aguardando pagamento",
    "pagamento_aprovado": "Pagamento aprovado",
    "aguardando_arquivos": "Aguardando arquivos",
    "em_personalizacao": "Em personalização",
    "aguardando_aprovacao": "Aguardando aprovação do cliente",
    "aprovado_cliente": "Aprovado pelo cliente",
    "em_pre_impressao": "Em pré-impressão",
    "aguardando_correcao": "Aguardando correção",
    "liberado_producao": "Liberado para produção",
    "em_producao": "Em produção",
    "finalizado": "Finalizado",
    "enviado": "Enviado",
    "entregue": "Entregue",
    "cancelado": "Cancelado",
}

router = APIRouter(prefix="/api")


def _jload(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _slugify(text: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return clean or f"item-{uuid4().hex[:6]}"


def _get_setting(db: Session, key: str, default: Any = None) -> Any:
    row = db.query(StoreSetting).filter(StoreSetting.key == key).first()
    if not row:
        return default if default is not None else {}
    return _jload(row.value_json, default if default is not None else {})


def _serialize_user(user: User, role: Role | None) -> dict[str, Any]:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "document_cpf_cnpj": user.document_cpf_cnpj,
        "is_active": user.is_active,
        "role_id": user.role_id,
        "role_slug": role.slug if role else "customer",
        "role_name": role.name if role else "Cliente",
        "is_staff": bool(role and role.slug != "customer"),
        "permissions": resolve_user_permissions(user, role),
        "custom_permissions": _jload(user.custom_permissions_json, {}),
        "lgpd_consent": user.lgpd_consent,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _serialize_product(db: Session, p: Product, include_variations: bool = True) -> dict[str, Any]:
    cat = db.query(Category).filter(Category.id == p.category_id).first()
    vars_list = []
    if include_variations:
        v_rows = (
            db.query(ProductVariation)
            .filter(ProductVariation.product_id == p.id, ProductVariation.is_active == True)
            .order_by(ProductVariation.sort_order.asc(), ProductVariation.id.asc())
            .all()
        )
        for v in v_rows:
            vars_list.append(
                {
                    "id": v.id,
                    "name": v.name,
                    "sku_suffix": v.sku_suffix,
                    "format_label": v.format_label,
                    "width_mm": v.width_mm,
                    "height_mm": v.height_mm,
                    "is_dated": v.is_dated,
                    "price_delta": v.price_delta,
                    "page_count_override": v.page_count_override,
                }
            )
    specs = _jload(p.specs_json, {})
    rules = _jload(p.pricing_rules_json, {})
    tools = normalize_editor_tools(_jload(p.allowed_tools_json, EDITOR_PROFILE_BASIC))
    effective_price = float(p.promo_price) if (p.promo_price and p.promo_price < p.base_price) else float(p.base_price)
    return {
        "id": p.id,
        "name": p.name,
        "sku": p.sku,
        "slug": p.slug,
        "category_id": p.category_id,
        "category_name": cat.name if cat else "",
        "category_slug": cat.slug if cat else "",
        "short_description": p.short_description,
        "full_description": p.full_description,
        "images": _jload(p.images_json, []),
        "mockups": _jload(p.mockups_json, []),
        "demo_file_url": p.demo_file_url,
        "base_price": p.base_price,
        "promo_price": p.promo_price,
        "effective_price": effective_price,
        "cost_price": p.cost_price,
        "product_type": p.product_type,
        "status": p.status,
        "is_available": p.is_available,
        "stock_qty": p.stock_qty,
        "is_featured": p.is_featured,
        "commercial_tag": p.commercial_tag,
        "is_customizable": p.is_customizable,
        "template_id": p.template_id,
        "allowed_tools": tools,
        "pricing_rules": rules,
        "specs": specs,
        "sales_count": p.sales_count,
        "variations": vars_list,
    }


def _get_or_create_cart(db: Session, auth: AuthContext | None, session_token: str | None) -> Cart:
    if auth:
        user_cart = db.query(Cart).filter(Cart.user_id == auth.user.id).first()
        if session_token:
            guest_cart = db.query(Cart).filter(Cart.session_token == session_token, Cart.user_id == None).first()
            if guest_cart:
                if not user_cart:
                    guest_cart.user_id = auth.user.id
                    db.commit()
                    db.refresh(guest_cart)
                    return guest_cart
                # Mescla itens do carrinho de visitante no carrinho do usuário logado
                guest_items = db.query(CartItem).filter(CartItem.cart_id == guest_cart.id).all()
                for gi in guest_items:
                    gi.cart_id = user_cart.id
                db.delete(guest_cart)
                db.commit()
        if user_cart:
            return user_cart
        cart = Cart(user_id=auth.user.id, session_token=session_token or "")
        db.add(cart)
        db.commit()
        db.refresh(cart)
        return cart

    tok = (session_token or "").strip() or uuid4().hex
    cart = db.query(Cart).filter(Cart.session_token == tok, Cart.user_id == None).first()
    if not cart:
        cart = Cart(user_id=None, session_token=tok)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def _build_cart_summary(db: Session, cart: Cart, user_id: int | None = None) -> dict[str, Any]:
    rows = db.query(CartItem).filter(CartItem.cart_id == cart.id).order_by(CartItem.id.asc()).all()
    items_out = []
    subtotal = 0.0
    for ci in rows:
        prod = db.query(Product).filter(Product.id == ci.product_id).first()
        if not prod:
            continue
        var = db.query(ProductVariation).filter(ProductVariation.id == ci.variation_id).first() if ci.variation_id else None
        proj = db.query(Project).filter(Project.id == ci.project_id).first() if ci.project_id else None
        cfg = _jload(proj.config_json, None) if proj else None
        opts = _jload(ci.selected_options_json, {})
        calc = calculate_item_price(prod, var, cfg, opts, ci.quantity, ci.is_customized)
        ci.unit_price_cached = calc["unit_price"]
        subtotal = round(subtotal + calc["total_price"], 2)
        imgs = _jload(prod.images_json, [])
        items_out.append(
            {
                "id": ci.id,
                "product_id": prod.id,
                "category_id": prod.category_id,
                "product_name": prod.name,
                "product_slug": prod.slug,
                "image_url": imgs[0] if imgs else "",
                "variation_id": var.id if var else None,
                "variation_name": var.name if var else "",
                "project_id": proj.id if proj else None,
                "project_name": proj.name if proj else "",
                "project_version": ci.project_version or (proj.version if proj else None),
                "is_customized": ci.is_customized,
                "selected_options": opts,
                "quantity": ci.quantity,
                "unit_price": calc["unit_price"],
                "total_price": calc["total_price"],
                "pricing_breakdown": calc,
            }
        )
    db.commit()

    ship_cfg = _get_setting(db, "payment_shipping", {})
    shipping_total = calculate_shipping(subtotal, cart.zip_code, ship_cfg)
    coupon_res = validate_and_apply_coupon(db, cart.coupon_code, user_id, items_out, subtotal, shipping_total)
    discount_total = coupon_res["discount_total"] if coupon_res["valid"] else 0.0
    effective_shipping = coupon_res["shipping_total"] if coupon_res["valid"] else shipping_total
    total_amount = round(max(0.0, subtotal - discount_total + effective_shipping), 2)

    return {
        "cart_id": cart.id,
        "session_token": cart.session_token,
        "items": items_out,
        "item_count": sum(i["quantity"] for i in items_out),
        "subtotal": subtotal,
        "discount_total": discount_total,
        "shipping_total": effective_shipping,
        "total_amount": total_amount,
        "zip_code": cart.zip_code,
        "coupon_code": cart.coupon_code,
        "coupon_info": coupon_res,
    }


def _record_order_status(
    db: Session,
    order: Order,
    new_status: str,
    actor_id: int | None = None,
    note: str = "",
) -> None:
    old = order.status
    order.status = new_status
    if new_status in ("finalizado", "entregue"):
        order.completed_at = datetime.now(timezone.utc)
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            from_status=old,
            to_status=new_status,
            changed_by_id=actor_id,
            note=note,
        )
    )


def _generate_item_pdf_files_sync(
    db: Session,
    order: Order,
    item: OrderItem,
    include_bleed: bool = True,
    include_crop_marks: bool = True,
    actor_id: int | None = None,
) -> dict[str, Any]:
    """Executa preflight e gera PDFs separados de Pré-Visualização e Impressão Final CMYK."""
    PRIVATE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    previews_dir = PRIVATE_STORAGE_DIR / "previews"
    final_dir = PRIVATE_STORAGE_DIR / "final_print"
    previews_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    cfg = _jload(item.immutable_config_snapshot_json, default_project_config())
    preflight = run_preflight(cfg)
    item.preflight_report_json = json.dumps(preflight, ensure_ascii=False)

    # 1. PDF de Pré-Visualização (amostra de conferência separada do arquivo final)
    gen = generate_agenda_pages(cfg)
    pages = gen["pages"]
    sample_pages = pages[: min(12, len(pages))]
    preview_bytes = render_pages_to_pdf_bytes(
        cfg,
        sample_pages,
        include_bleed=False,
        include_crop_marks=False,
        mirror_margins=bool(cfg.get("page_setup", {}).get("mirror_margins", True)),
        title=f"Prévia - Pedido {order.order_number} - {item.product_name}",
    )
    prev_name = f"prev_{order.order_number}_item{item.id}_v{item.project_version or 1}_{uuid4().hex[:6]}.pdf"
    prev_path = previews_dir / prev_name
    prev_path.write_bytes(preview_bytes)
    prev_media = MediaFile(
        owner_id=order.user_id,
        order_id=order.id,
        project_id=item.project_id,
        folder="previews",
        category="pdf_preview",
        original_name=f"Previa_{order.order_number}_{item.sku}.pdf",
        stored_path=str(prev_path.relative_to(BASE_DIR)),
        mime_type="application/pdf",
        size_bytes=len(preview_bytes),
        is_private=True,
        version=item.project_version or 1,
    )
    db.add(prev_media)
    db.flush()
    item.preview_file_id = prev_media.id

    # 2. PDF Final de Impressão CMYK (completo com sangria e marcas de corte)
    final_bytes, mime_t, _ = export_project_bundle(
        config=cfg,
        export_mode="single_pdf",
        include_bleed=include_bleed,
        include_crop_marks=include_crop_marks,
        mirror_margins=bool(cfg.get("page_setup", {}).get("mirror_margins", True)),
        project_name=f"Final_{order.order_number}_{item.sku}",
    )
    fin_name = f"final_{order.order_number}_item{item.id}_v{item.project_version or 1}_{uuid4().hex[:6]}.pdf"
    fin_path = final_dir / fin_name
    fin_path.write_bytes(final_bytes)
    fin_media = MediaFile(
        owner_id=order.user_id,
        order_id=order.id,
        project_id=item.project_id,
        folder="final_print",
        category="pdf_final",
        original_name=f"Impressao_CMYK_{order.order_number}_{item.sku}.pdf",
        stored_path=str(fin_path.relative_to(BASE_DIR)),
        mime_type=mime_t,
        size_bytes=len(final_bytes),
        is_private=True,
        version=item.project_version or 1,
    )
    db.add(fin_media)
    db.flush()
    item.final_file_id = fin_media.id

    if item.artwork_status in ("pending", "changes_requested"):
        item.artwork_status = "awaiting_approval"
        if order.status in ("pagamento_aprovado", "em_personalizacao", "aguardando_arquivos", "aguardando_correcao"):
            _record_order_status(db, order, "aguardando_aprovacao", actor_id, "Prévia e arquivo CMYK gerados para aprovação do cliente.")
        create_notification_once(
            db,
            order.user_id,
            "artwork_awaiting_approval",
            f"Arte pronta para aprovação — Pedido {order.order_number}",
            f"A prévia de '{item.product_name}' está disponível na Área do Cliente para sua conferência e aprovação.",
            dedup_key=f"art_ready_{order.id}_{item.id}_v{item.project_version or 1}",
        )

    db.commit()
    return {
        "order_id": order.id,
        "item_id": item.id,
        "preview_file_id": prev_media.id,
        "final_file_id": fin_media.id,
        "preflight": preflight,
        "artwork_status": item.artwork_status,
    }


def _bg_generate_order_files(order_id: int, item_id: int, include_bleed: bool, include_crop_marks: bool, actor_id: int | None) -> None:
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        item = db.query(OrderItem).filter(OrderItem.id == item_id, OrderItem.order_id == order_id).first()
        if order and item:
            _generate_item_pdf_files_sync(db, order, item, include_bleed, include_crop_marks, actor_id)
    finally:
        db.close()


# ==================== SCHEMAS PYDANTIC ====================


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=180)
    email: str = Field(..., min_length=4, max_length=200)
    password: str = Field(..., min_length=6, max_length=128)
    phone: str = ""
    document_cpf_cnpj: str = ""
    lgpd_consent: bool = True


class LoginRequest(BaseModel):
    email: str
    password: str


class RecoverPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    token: str
    new_password: str = Field(..., min_length=6, max_length=128)


class AddressPayload(BaseModel):
    label: str = "Principal"
    recipient_name: str
    street: str
    number: str
    complement: str = ""
    neighborhood: str = ""
    city: str
    state: str
    zip_code: str
    is_default: bool = True


class PriceCalcRequest(BaseModel):
    product_id: int
    variation_id: Optional[int] = None
    quantity: int = Field(1, ge=1, le=5000)
    is_customized: bool = False
    selected_options: dict[str, Any] = Field(default_factory=dict)
    project_id: Optional[int] = None


class StartCustomizerRequest(BaseModel):
    product_id: int
    variation_id: Optional[int] = None
    selected_options: dict[str, Any] = Field(default_factory=dict)
    project_name: Optional[str] = None


class SaveCustomProjectRequest(BaseModel):
    name: Optional[str] = None
    config: dict[str, Any]
    selected_options: Optional[dict[str, Any]] = None
    create_version: bool = False
    version_note: str = ""


class AddCartItemRequest(BaseModel):
    product_id: int
    variation_id: Optional[int] = None
    project_id: Optional[int] = None
    is_customized: bool = False
    selected_options: dict[str, Any] = Field(default_factory=dict)
    quantity: int = Field(1, ge=1, le=5000)


class UpdateCartItemQtyRequest(BaseModel):
    quantity: int = Field(..., ge=1, le=5000)


class ApplyCouponRequest(BaseModel):
    coupon_code: str


class UpdateShippingZipRequest(BaseModel):
    zip_code: str


class CheckoutRequest(BaseModel):
    address_id: Optional[int] = None
    address: Optional[AddressPayload] = None
    payment_method: str = Field("pix", pattern="^(pix|mercadopago)$")
    customer_notes: str = ""


class ArtworkDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|changes_requested)$")
    comments: str = ""


class OrderStatusUpdateRequest(BaseModel):
    status: str
    note: str = ""
    priority: Optional[str] = None
    internal_notes: Optional[str] = None


class OrderAssignRequest(BaseModel):
    editor_user_id: int


class CategoryPayload(BaseModel):
    name: str
    slug: Optional[str] = None
    description: str = ""
    image_url: str = ""
    sort_order: int = 0
    is_active: bool = True


class ProductVariationPayload(BaseModel):
    name: str
    sku_suffix: str = ""
    format_label: str = "15 x 21 cm (A5)"
    width_mm: float = 150.0
    height_mm: float = 210.0
    is_dated: bool = True
    price_delta: float = 0.0
    page_count_override: Optional[int] = None


class ProductPayload(BaseModel):
    name: str
    sku: str
    slug: Optional[str] = None
    category_id: int
    short_description: str = ""
    full_description: str = ""
    images: list[str] = Field(default_factory=list)
    mockups: list[str] = Field(default_factory=list)
    demo_file_url: str = ""
    base_price: float = Field(..., gt=0)
    promo_price: Optional[float] = None
    cost_price: float = 0.0
    product_type: str = "hybrid"
    status: str = "active"
    is_available: bool = True
    stock_qty: int = 500
    is_featured: bool = False
    commercial_tag: str = ""
    is_customizable: bool = True
    template_id: Optional[int] = None
    allowed_tools: dict[str, bool] = Field(default_factory=dict)
    pricing_rules: dict[str, Any] = Field(default_factory=dict)
    specs: dict[str, Any] = Field(default_factory=dict)
    variations: list[ProductVariationPayload] = Field(default_factory=list)


class TemplatePayload(BaseModel):
    name: str
    slug: Optional[str] = None
    description: str = ""
    category_slug: str = "agendas-diarias"
    base_layout_mode: str = "1_dpp"
    status: str = "published"
    allowed_tools: dict[str, bool] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=default_project_config)
    changelog: str = "Nova versão"


class RolePayload(BaseModel):
    name: str
    slug: Optional[str] = None
    description: str = ""
    permissions: dict[str, list[str]] = Field(default_factory=dict)


class UserAdminUpdatePayload(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None
    custom_permissions: Optional[dict[str, Any]] = None


class UserAdminCreatePayload(BaseModel):
    name: str
    email: str
    password: str = Field(..., min_length=6)
    phone: str = ""
    role_id: int


class CouponPayload(BaseModel):
    code: str
    description: str = ""
    discount_type: str = "percent"
    discount_value: float = 10.0
    min_order_value: float = 0.0
    min_quantity: int = 1
    max_uses: Optional[int] = None
    max_uses_per_user: Optional[int] = None
    is_active: bool = True
    eligible_product_ids: list[int] = Field(default_factory=list)
    eligible_category_ids: list[int] = Field(default_factory=list)


class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=5)
    order_id: Optional[int] = None


class SupportTicketReply(BaseModel):
    status: str = "resolved"
    admin_reply: str


# ==================== AUTENTICAÇÃO & LGPD ====================


@router.post("/auth/register", status_code=201)
def register_customer(
    payload: RegisterRequest,
    request: Request,
    x_cart_session: str | None = Header(None),
    db: Session = Depends(get_db),
):
    check_rate_limit("register", request.client.host if request.client else "local", max_calls=15, window_sec=60)
    if not payload.lgpd_consent:
        raise HTTPException(status_code=400, detail="É necessário aceitar a Política de Privacidade (LGPD).")
    email = payload.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.")
    cust_role = db.query(Role).filter(Role.slug == "customer").first()
    if not cust_role:
        raise HTTPException(status_code=500, detail="Perfil padrão de cliente não encontrado.")

    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        phone=payload.phone.strip(),
        document_cpf_cnpj=payload.document_cpf_cnpj.strip(),
        role_id=cust_role.id,
        is_active=True,
        lgpd_consent=True,
        lgpd_consent_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()
    create_notification_once(
        db,
        user.id,
        "user_registered",
        "Bem-vindo ao EditorGráfica Atelier",
        "Sua conta foi criada com sucesso. Você já pode personalizar seus miolos e acompanhar pedidos.",
        dedup_key=f"welcome_{user.id}",
    )
    db.commit()
    db.refresh(user)
    auth_ctx = AuthContext(user, cust_role)
    if x_cart_session:
        _get_or_create_cart(db, auth_ctx, x_cart_session)
    token = create_access_token(user.id, cust_role.slug)
    return {"access_token": token, "token_type": "bearer", "user": _serialize_user(user, cust_role)}


@router.post("/auth/login")
def login_user(
    payload: LoginRequest,
    request: Request,
    x_cart_session: str | None = Header(None),
    db: Session = Depends(get_db),
):
    check_rate_limit("login", request.client.host if request.client else "local", max_calls=25, window_sec=60)
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
    if not user.is_active or user.is_anonymized:
        raise HTTPException(status_code=403, detail="Esta conta está desativada.")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    auth_ctx = AuthContext(user, role)
    if x_cart_session:
        _get_or_create_cart(db, auth_ctx, x_cart_session)
    token = create_access_token(user.id, role.slug if role else "customer")
    log_audit(db, "auth.login", "user", user.id, {"email": email}, auth_ctx, request)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": _serialize_user(user, role)}


@router.get("/auth/me")
def get_me(auth: AuthContext = Depends(get_current_auth)):
    return {"user": _serialize_user(auth.user, auth.role)}


@router.post("/auth/recover-password")
def recover_password(payload: RecoverPasswordRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit("recover", request.client.host if request.client else "local", max_calls=10, window_sec=60)
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user and user.is_active:
        import hashlib
        from datetime import timedelta

        raw_tok = uuid4().hex[:8].upper()
        user.reset_token_hash = hashlib.sha256(raw_tok.encode()).hexdigest()
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        create_notification_once(
            db,
            user.id,
            "password_recovery",
            "Código de recuperação de senha",
            f"Código temporário de recuperação: {raw_tok} (válido por 30 minutos).",
            dedup_key=f"pw_reset_{user.id}_{raw_tok}",
            channel="email",
        )
        db.commit()
    return {"sent": True, "message": "Se o e-mail existir, enviamos as instruções de recuperação."}


@router.post("/auth/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    import hashlib

    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.reset_token_hash:
        raise HTTPException(status_code=400, detail="Solicitação de recuperação inválida.")
    exp = user.reset_token_expires_at
    if exp and (exp if exp.tzinfo else exp.replace(tzinfo=timezone.utc)) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Código expirado.")
    tok_hash = hashlib.sha256(payload.token.strip().upper().encode()).hexdigest()
    if tok_hash != user.reset_token_hash:
        raise HTTPException(status_code=400, detail="Código de recuperação inválido.")
    user.password_hash = hash_password(payload.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    db.commit()
    return {"reset": True}


@router.get("/lgpd/my-data")
def lgpd_export_my_data(auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    addrs = db.query(CustomerAddress).filter(CustomerAddress.user_id == auth.user.id).all()
    orders = db.query(Order).filter(Order.user_id == auth.user.id).all()
    projs = db.query(Project).filter(Project.owner_id == auth.user.id).all()
    return {
        "user": _serialize_user(auth.user, auth.role),
        "addresses": [{"id": a.id, "street": a.street, "city": a.city, "zip_code": a.zip_code} for a in addrs],
        "orders": [{"id": o.id, "order_number": o.order_number, "total_amount": o.total_amount, "status": o.status} for o in orders],
        "projects": [{"id": p.id, "name": p.name, "version": p.version} for p in projs],
    }


@router.post("/lgpd/anonymize")
def lgpd_anonymize_me(auth: AuthContext = Depends(get_current_auth), request: Request = None, db: Session = Depends(get_db)):
    if auth.is_admin:
        raise HTTPException(status_code=400, detail="Administradores não podem ser anonimizados por esta rota.")
    uid = auth.user.id
    auth.user.name = f"Usuário Anonimizado #{uid}"
    auth.user.email = f"anon_{uid}_{uuid4().hex[:6]}@anonymized.local"
    auth.user.phone = ""
    auth.user.document_cpf_cnpj = ""
    auth.user.is_active = False
    auth.user.is_anonymized = True
    log_audit(db, "lgpd.anonymize", "user", uid, {}, auth, request)
    db.commit()
    return {"anonymized": True}


# ==================== LOJA VIRTUAL & CATÁLOGO ====================


@router.get("/store/home")
def get_store_home(db: Session = Depends(get_db)):
    categories = db.query(Category).filter(Category.is_active == True).order_by(Category.sort_order.asc()).all()
    active_prods = db.query(Product).filter(Product.status == "active", Product.is_available == True).all()
    serialized = [_serialize_product(db, p, include_variations=True) for p in active_prods]
    return {
        "store_identity": _get_setting(db, "store_identity", {}),
        "home_content": _get_setting(db, "home_content", {}),
        "payment_shipping": _get_setting(db, "payment_shipping", {}),
        "policies": _get_setting(db, "policies", {}),
        "categories": [
            {"id": c.id, "name": c.name, "slug": c.slug, "description": c.description, "image_url": c.image_url}
            for c in categories
        ],
        "featured_products": [p for p in serialized if p["is_featured"]][:8],
        "bestsellers": sorted(serialized, key=lambda x: x["sales_count"], reverse=True)[:4],
        "new_arrivals": [p for p in serialized if p["commercial_tag"] == "new"][:4] or serialized[-4:],
        "customizable_products": [p for p in serialized if p["is_customizable"]][:6],
    }


@router.get("/store/categories")
def list_store_categories(db: Session = Depends(get_db)):
    cats = db.query(Category).filter(Category.is_active == True).order_by(Category.sort_order.asc()).all()
    return {"categories": [{"id": c.id, "name": c.name, "slug": c.slug, "description": c.description, "image_url": c.image_url} for c in cats]}


@router.get("/store/products")
def list_store_products(
    q: str = "",
    category: str = "",
    format_filter: str = "",
    layout_type: str = "",
    orientation: str = "",
    min_price: float | None = None,
    max_price: float | None = None,
    only_available: bool = True,
    only_customizable: bool = False,
    sort: str = "relevance",
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Product).filter(Product.status == "active")
    if only_available:
        query = query.filter(Product.is_available == True)
    if only_customizable:
        query = query.filter(Product.is_customizable == True)

    all_prods = [_serialize_product(db, p, include_variations=True) for p in query.all()]
    q_low = q.strip().lower()
    cat_low = category.strip().lower()
    fmt_low = format_filter.strip().lower()
    lay_low = layout_type.strip().lower()
    ori_low = orientation.strip().lower()

    filtered = []
    for p in all_prods:
        if q_low and q_low not in p["name"].lower() and q_low not in p["short_description"].lower() and q_low not in p["sku"].lower():
            continue
        if cat_low and cat_low != "all" and p["category_slug"].lower() != cat_low:
            continue
        if fmt_low:
            dims = (p["specs"].get("dimensions") or "").lower()
            v_match = any(fmt_low in v["format_label"].lower() or fmt_low in v["name"].lower() for v in p["variations"])
            if fmt_low not in dims and not v_match:
                continue
        if lay_low and lay_low not in (p["specs"].get("ruling_type") or "").lower() and lay_low not in p["name"].lower():
            continue
        if ori_low and ori_low != (p["specs"].get("orientation") or "portrait").lower():
            continue
        if min_price is not None and p["effective_price"] < min_price:
            continue
        if max_price is not None and p["effective_price"] > max_price:
            continue
        filtered.append(p)

    if sort == "bestsellers":
        filtered.sort(key=lambda x: x["sales_count"], reverse=True)
    elif sort == "newest":
        filtered.sort(key=lambda x: x["id"], reverse=True)
    elif sort == "price_asc":
        filtered.sort(key=lambda x: x["effective_price"])
    elif sort == "price_desc":
        filtered.sort(key=lambda x: x["effective_price"], reverse=True)
    else:
        filtered.sort(key=lambda x: (not x["is_featured"], -x["sales_count"]))

    total = len(filtered)
    start = (page - 1) * page_size
    return {"total": total, "page": page, "page_size": page_size, "products": filtered[start : start + page_size]}


@router.get("/store/products/{slug_or_id}")
def get_store_product(slug_or_id: str, db: Session = Depends(get_db)):
    if slug_or_id.isdigit():
        prod = db.query(Product).filter(Product.id == int(slug_or_id)).first()
    else:
        prod = db.query(Product).filter(Product.slug == slug_or_id).first()
    if not prod or prod.status == "archived":
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return {"product": _serialize_product(db, prod, include_variations=True), "tool_labels": EDITOR_TOOL_LABELS}


@router.post("/store/calculate-price")
def api_calculate_price(payload: PriceCalcRequest, db: Session = Depends(get_db)):
    prod = db.query(Product).filter(Product.id == payload.product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    var = db.query(ProductVariation).filter(ProductVariation.id == payload.variation_id, ProductVariation.product_id == prod.id).first() if payload.variation_id else None
    cfg = None
    if payload.project_id:
        proj = db.query(Project).filter(Project.id == payload.project_id).first()
        if proj:
            cfg = _jload(proj.config_json, None)
    return calculate_item_price(prod, var, cfg, payload.selected_options, payload.quantity, payload.is_customized)


# ==================== EDITOR DE PERSONALIZAÇÃO PARA CLIENTES ====================


@router.post("/customizer/start", status_code=201)
def start_customizer_project(
    payload: StartCustomizerRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    prod = db.query(Product).filter(Product.id == payload.product_id).first()
    if not prod or not prod.is_customizable:
        raise HTTPException(status_code=400, detail="Este produto não permite personalização no editor.")

    var = None
    if payload.variation_id:
        var = db.query(ProductVariation).filter(ProductVariation.id == payload.variation_id, ProductVariation.product_id == prod.id).first()

    tpl_version_num = 1
    base_cfg = default_project_config()
    if prod.template_id:
        tpl = db.query(GraphicTemplate).filter(GraphicTemplate.id == prod.template_id).first()
        if tpl:
            ver_row = (
                db.query(GraphicTemplateVersion)
                .filter(GraphicTemplateVersion.template_id == tpl.id, GraphicTemplateVersion.is_published == True)
                .order_by(GraphicTemplateVersion.version_number.desc())
                .first()
            )
            if ver_row:
                tpl_version_num = ver_row.version_number
                base_cfg = _jload(ver_row.config_json, base_cfg)

    cfg = copy.deepcopy(base_cfg)
    if var:
        cfg["page_setup"]["width_mm"] = float(var.width_mm)
        cfg["page_setup"]["height_mm"] = float(var.height_mm)
        cfg["calendar"]["is_dated"] = bool(var.is_dated)

    validated_cfg = ProjectConfig.model_validate(cfg).model_dump()
    gen = generate_agenda_pages(validated_cfg)
    pname = (payload.project_name or f"{prod.name} — {auth.user.name.split()[0]}").strip()

    proj = Project(
        name=pname[:190],
        client_name=auth.user.name,
        description=f"Personalização de {prod.name}",
        year=int(validated_cfg["calendar"]["year"]),
        template_type=validated_cfg["calendar"]["layout_mode"],
        format_name=var.format_label if var else prod.specs_json[:40],
        config_json=json.dumps(validated_cfg, ensure_ascii=False),
        page_count=gen["total_pages"],
        owner_id=auth.user.id,
        product_id=prod.id,
        template_id=prod.template_id,
        template_version=tpl_version_num,
        version=1,
        status="draft",
        customization_options_json=json.dumps({"variation_id": var.id if var else None, **payload.selected_options}, ensure_ascii=False),
    )
    db.add(proj)
    db.flush()
    db.add(
        ProjectVersion(
            project_id=proj.id,
            version_number=1,
            config_json=proj.config_json,
            customization_options_json=proj.customization_options_json,
            saved_by_id=auth.user.id,
            note="Versão inicial criada a partir do modelo publicado",
        )
    )
    db.commit()
    db.refresh(proj)

    allowed_tools = normalize_editor_tools(_jload(prod.allowed_tools_json, EDITOR_PROFILE_BASIC))
    if auth.is_staff:
        allowed_tools = {k: True for k in EDITOR_TOOL_LABELS}
    pricing = calculate_item_price(prod, var, validated_cfg, payload.selected_options, 1, is_customized=True)
    return {
        "project": {
            "id": proj.id,
            "name": proj.name,
            "version": proj.version,
            "product_id": proj.product_id,
            "template_version": proj.template_version,
            "page_count": proj.page_count,
            "config": validated_cfg,
            "customization_options": _jload(proj.customization_options_json, {}),
        },
        "allowed_tools": allowed_tools,
        "tool_labels": EDITOR_TOOL_LABELS,
        "pricing": pricing,
    }


@router.get("/customizer/projects/{project_id}")
def get_customizer_project(
    project_id: int,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    ensure_owner_or_staff(auth, proj.owner_id, "projects", "read")

    prod = db.query(Product).filter(Product.id == proj.product_id).first() if proj.product_id else None
    allowed_tools = {k: True for k in EDITOR_TOOL_LABELS} if auth.is_staff else normalize_editor_tools(_jload(prod.allowed_tools_json, EDITOR_PROFILE_BASIC) if prod else EDITOR_PROFILE_BASIC)
    versions = (
        db.query(ProjectVersion)
        .filter(ProjectVersion.project_id == proj.id)
        .order_by(ProjectVersion.version_number.desc())
        .limit(20)
        .all()
    )
    cfg = _jload(proj.config_json, default_project_config())
    opts = _jload(proj.customization_options_json, {})
    var_id = opts.get("variation_id")
    var = db.query(ProductVariation).filter(ProductVariation.id == var_id).first() if var_id else None
    pricing = calculate_item_price(prod, var, cfg, opts, 1, True) if prod else None

    return {
        "project": {
            "id": proj.id,
            "name": proj.name,
            "client_name": proj.client_name,
            "version": proj.version,
            "status": proj.status,
            "product_id": proj.product_id,
            "template_version": proj.template_version,
            "page_count": proj.page_count,
            "config": cfg,
            "customization_options": opts,
        },
        "product": _serialize_product(db, prod, include_variations=True) if prod else None,
        "allowed_tools": allowed_tools,
        "tool_labels": EDITOR_TOOL_LABELS,
        "pricing": pricing,
        "versions": [
            {"version_number": v.version_number, "note": v.note, "created_at": v.created_at.isoformat()}
            for v in versions
        ],
    }


@router.put("/customizer/projects/{project_id}")
def save_customizer_project(
    project_id: int,
    payload: SaveCustomProjectRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    ensure_owner_or_staff(auth, proj.owner_id, "projects", "edit")

    old_cfg = _jload(proj.config_json, default_project_config())
    new_cfg = ProjectConfig.model_validate(payload.config).model_dump()

    prod = db.query(Product).filter(Product.id == proj.product_id).first() if proj.product_id else None
    if not auth.is_staff and prod:
        allowed_tools = normalize_editor_tools(_jload(prod.allowed_tools_json, EDITOR_PROFILE_BASIC))
        enforce_editor_tool_permissions(old_cfg, new_cfg, allowed_tools)

    gen = generate_agenda_pages(new_cfg)
    if payload.name:
        proj.name = payload.name.strip()[:190]
    proj.config_json = json.dumps(new_cfg, ensure_ascii=False)
    proj.year = int(new_cfg["calendar"]["year"])
    proj.template_type = new_cfg["calendar"]["layout_mode"]
    proj.page_count = gen["total_pages"]
    if payload.selected_options is not None:
        proj.customization_options_json = json.dumps(payload.selected_options, ensure_ascii=False)

    if payload.create_version:
        proj.version = int(proj.version or 1) + 1
        db.add(
            ProjectVersion(
                project_id=proj.id,
                version_number=proj.version,
                config_json=proj.config_json,
                customization_options_json=proj.customization_options_json,
                saved_by_id=auth.user.id,
                note=payload.version_note or f"Salvamento v{proj.version}",
            )
        )

    db.commit()
    db.refresh(proj)

    opts = _jload(proj.customization_options_json, {})
    var = db.query(ProductVariation).filter(ProductVariation.id == opts.get("variation_id")).first() if opts.get("variation_id") else None
    pricing = calculate_item_price(prod, var, new_cfg, opts, 1, True) if prod else None

    return {
        "saved": True,
        "version": proj.version,
        "page_count": proj.page_count,
        "pricing": pricing,
    }


@router.post("/customizer/projects/{project_id}/restore-version/{version_number}")
def restore_project_version(
    project_id: int,
    version_number: int,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    ensure_owner_or_staff(auth, proj.owner_id, "projects", "edit")
    ver = db.query(ProjectVersion).filter(ProjectVersion.project_id == project_id, ProjectVersion.version_number == version_number).first()
    if not ver:
        raise HTTPException(status_code=404, detail="Versão não encontrada.")

    proj.config_json = ver.config_json
    proj.customization_options_json = ver.customization_options_json
    proj.version = int(proj.version or 1) + 1
    db.add(
        ProjectVersion(
            project_id=proj.id,
            version_number=proj.version,
            config_json=proj.config_json,
            customization_options_json=proj.customization_options_json,
            saved_by_id=auth.user.id,
            note=f"Restaurado da versão v{version_number}",
        )
    )
    db.commit()
    return {"restored": True, "version": proj.version, "config": _jload(proj.config_json, {})}


@router.post("/customizer/projects/{project_id}/preflight")
def customizer_preflight(
    project_id: int,
    config_override: dict[str, Any] | None = None,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    ensure_owner_or_staff(auth, proj.owner_id, "projects", "read")
    cfg = ProjectConfig.model_validate(config_override).model_dump() if config_override else _jload(proj.config_json, default_project_config())
    return run_preflight(cfg)


@router.post("/customizer/projects/{project_id}/preview-pdf")
def customizer_preview_pdf(
    project_id: int,
    page_number: int = Query(1, ge=1),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    ensure_owner_or_staff(auth, proj.owner_id, "projects", "read")
    if not auth.is_staff and proj.product_id:
        prod = db.query(Product).filter(Product.id == proj.product_id).first()
        tools = normalize_editor_tools(_jload(prod.allowed_tools_json, EDITOR_PROFILE_BASIC) if prod else {})
        if not tools.get("export_preview"):
            raise HTTPException(status_code=403, detail="Exportação de prévia desabilitada para este produto.")
    cfg = _jload(proj.config_json, default_project_config())
    gen = generate_agenda_pages(cfg)
    pages = gen["pages"]
    idx = min(max(0, page_number - 1), len(pages) - 1)
    pdf_bytes = render_pages_to_pdf_bytes(cfg, [pages[idx]], include_bleed=True, include_crop_marks=False, title=f"Prévia {proj.name}")
    return Response(content=pdf_bytes, media_type="application/pdf")


# ==================== CARRINHO & CHECKOUT ====================


@router.get("/cart")
def get_cart(
    x_cart_session: str | None = Header(None),
    auth: AuthContext | None = Depends(get_optional_auth),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_cart(db, auth, x_cart_session)
    return _build_cart_summary(db, cart, auth.user.id if auth else None)


@router.post("/cart/items", status_code=201)
def add_to_cart(
    payload: AddCartItemRequest,
    x_cart_session: str | None = Header(None),
    auth: AuthContext | None = Depends(get_optional_auth),
    db: Session = Depends(get_db),
):
    prod = db.query(Product).filter(Product.id == payload.product_id, Product.status == "active").first()
    if not prod or not prod.is_available:
        raise HTTPException(status_code=404, detail="Produto indisponível.")
    var = db.query(ProductVariation).filter(ProductVariation.id == payload.variation_id, ProductVariation.product_id == prod.id).first() if payload.variation_id else None

    proj = None
    cfg = None
    if payload.project_id:
        proj = db.query(Project).filter(Project.id == payload.project_id).first()
        if not proj:
            raise HTTPException(status_code=404, detail="Projeto personalizado não encontrado.")
        if auth:
            ensure_owner_or_staff(auth, proj.owner_id, "projects", "read")
        cfg = _jload(proj.config_json, None)

    cart = _get_or_create_cart(db, auth, x_cart_session)
    calc = calculate_item_price(prod, var, cfg, payload.selected_options, payload.quantity, payload.is_customized or bool(proj))

    # Se não for personalizado, agrupa mesma variação+opções
    if not (payload.is_customized or proj):
        existing = (
            db.query(CartItem)
            .filter(
                CartItem.cart_id == cart.id,
                CartItem.product_id == prod.id,
                CartItem.variation_id == (var.id if var else None),
                CartItem.is_customized == False,
                CartItem.selected_options_json == json.dumps(payload.selected_options, ensure_ascii=False),
            )
            .first()
        )
        if existing:
            existing.quantity += payload.quantity
            db.commit()
            return _build_cart_summary(db, cart, auth.user.id if auth else None)

    if proj:
        proj.status = "in_cart"
    db.add(
        CartItem(
            cart_id=cart.id,
            product_id=prod.id,
            variation_id=var.id if var else None,
            project_id=proj.id if proj else None,
            project_version=proj.version if proj else None,
            is_customized=bool(payload.is_customized or proj),
            selected_options_json=json.dumps(payload.selected_options, ensure_ascii=False),
            quantity=payload.quantity,
            unit_price_cached=calc["unit_price"],
        )
    )
    db.commit()
    return _build_cart_summary(db, cart, auth.user.id if auth else None)


@router.patch("/cart/items/{item_id}")
def update_cart_item_qty(
    item_id: int,
    payload: UpdateCartItemQtyRequest,
    x_cart_session: str | None = Header(None),
    auth: AuthContext | None = Depends(get_optional_auth),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_cart(db, auth, x_cart_session)
    ci = db.query(CartItem).filter(CartItem.id == item_id, CartItem.cart_id == cart.id).first()
    if not ci:
        raise HTTPException(status_code=404, detail="Item do carrinho não encontrado.")
    ci.quantity = payload.quantity
    db.commit()
    return _build_cart_summary(db, cart, auth.user.id if auth else None)


@router.delete("/cart/items/{item_id}")
def delete_cart_item(
    item_id: int,
    x_cart_session: str | None = Header(None),
    auth: AuthContext | None = Depends(get_optional_auth),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_cart(db, auth, x_cart_session)
    ci = db.query(CartItem).filter(CartItem.id == item_id, CartItem.cart_id == cart.id).first()
    if not ci:
        raise HTTPException(status_code=404, detail="Item do carrinho não encontrado.")
    db.delete(ci)
    db.commit()
    return _build_cart_summary(db, cart, auth.user.id if auth else None)


@router.post("/cart/coupon")
def apply_cart_coupon(
    payload: ApplyCouponRequest,
    x_cart_session: str | None = Header(None),
    auth: AuthContext | None = Depends(get_optional_auth),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_cart(db, auth, x_cart_session)
    cart.coupon_code = payload.coupon_code.strip().upper()
    db.commit()
    summary = _build_cart_summary(db, cart, auth.user.id if auth else None)
    if cart.coupon_code and not summary["coupon_info"]["valid"]:
        raise HTTPException(status_code=400, detail=summary["coupon_info"]["reason"])
    return summary


@router.post("/cart/shipping")
def update_cart_shipping(
    payload: UpdateShippingZipRequest,
    x_cart_session: str | None = Header(None),
    auth: AuthContext | None = Depends(get_optional_auth),
    db: Session = Depends(get_db),
):
    cart = _get_or_create_cart(db, auth, x_cart_session)
    cart.zip_code = payload.zip_code.strip()
    db.commit()
    return _build_cart_summary(db, cart, auth.user.id if auth else None)


@router.post("/checkout", status_code=201)
def checkout_order(
    payload: CheckoutRequest,
    request: Request,
    x_cart_session: str | None = Header(None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    check_rate_limit("checkout", str(auth.user.id), max_calls=12, window_sec=60)
    cart = _get_or_create_cart(db, auth, x_cart_session)
    cart_rows = db.query(CartItem).filter(CartItem.cart_id == cart.id).all()
    if not cart_rows:
        raise HTTPException(status_code=400, detail="Seu carrinho está vazio.")

    # Endereço
    addr_dict: dict[str, Any] = {}
    if payload.address_id:
        addr = db.query(CustomerAddress).filter(CustomerAddress.id == payload.address_id, CustomerAddress.user_id == auth.user.id).first()
        if not addr:
            raise HTTPException(status_code=404, detail="Endereço não encontrado.")
        addr_dict = {
            "recipient_name": addr.recipient_name, "street": addr.street, "number": addr.number,
            "complement": addr.complement, "neighborhood": addr.neighborhood, "city": addr.city,
            "state": addr.state, "zip_code": addr.zip_code,
        }
    elif payload.address:
        addr_dict = payload.address.model_dump()
        db.add(CustomerAddress(user_id=auth.user.id, **addr_dict))
    else:
        default_addr = db.query(CustomerAddress).filter(CustomerAddress.user_id == auth.user.id).order_by(CustomerAddress.is_default.desc()).first()
        if not default_addr:
            raise HTTPException(status_code=400, detail="Informe um endereço de entrega.")
        addr_dict = {
            "recipient_name": default_addr.recipient_name, "street": default_addr.street, "number": default_addr.number,
            "complement": default_addr.complement, "neighborhood": default_addr.neighborhood, "city": default_addr.city,
            "state": default_addr.state, "zip_code": default_addr.zip_code,
        }

    cart.zip_code = addr_dict.get("zip_code", cart.zip_code)
    summary = _build_cart_summary(db, cart, auth.user.id)
    order_number = f"EG-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:5].upper()}"

    order = Order(
        order_number=order_number,
        user_id=auth.user.id,
        status="aguardando_pagamento",
        subtotal=summary["subtotal"],
        discount_total=summary["discount_total"],
        shipping_total=summary["shipping_total"],
        total_amount=summary["total_amount"],
        coupon_code=summary["coupon_code"] if summary["coupon_info"]["valid"] else "",
        shipping_address_json=json.dumps(addr_dict, ensure_ascii=False),
        payment_method=payload.payment_method,
        payment_status="pending",
        customer_notes=payload.customer_notes,
        pricing_rules_snapshot_json=json.dumps(summary["coupon_info"], ensure_ascii=False),
    )
    db.add(order)
    db.flush()

    for ci in cart_rows:
        prod = db.query(Product).filter(Product.id == ci.product_id).first()
        if not prod:
            continue
        var = db.query(ProductVariation).filter(ProductVariation.id == ci.variation_id).first() if ci.variation_id else None
        proj = db.query(Project).filter(Project.id == ci.project_id).first() if ci.project_id else None

        # Snapshot IMUTÁVEL da configuração (modelo ou projeto do cliente)
        if proj:
            snap_cfg = _jload(proj.config_json, default_project_config())
            proj.status = "ordered"
            proj_ver = proj.version
        else:
            tpl_cfg = default_project_config()
            if prod.template_id:
                ver_row = (
                    db.query(GraphicTemplateVersion)
                    .filter(GraphicTemplateVersion.template_id == prod.template_id, GraphicTemplateVersion.is_published == True)
                    .order_by(GraphicTemplateVersion.version_number.desc())
                    .first()
                )
                if ver_row:
                    tpl_cfg = _jload(ver_row.config_json, tpl_cfg)
            if var:
                tpl_cfg["page_setup"]["width_mm"] = float(var.width_mm)
                tpl_cfg["page_setup"]["height_mm"] = float(var.height_mm)
                tpl_cfg["calendar"]["is_dated"] = bool(var.is_dated)
            snap_cfg = tpl_cfg
            proj_ver = 1

        opts = _jload(ci.selected_options_json, {})
        calc = calculate_item_price(prod, var, snap_cfg, opts, ci.quantity, ci.is_customized)
        prod.sales_count = int(prod.sales_count or 0) + ci.quantity

        db.add(
            OrderItem(
                order_id=order.id,
                product_id=prod.id,
                variation_id=var.id if var else None,
                project_id=proj.id if proj else None,
                project_version=proj_ver,
                product_name=prod.name,
                variation_name=var.name if var else "",
                sku=f"{prod.sku}{var.sku_suffix if var else ''}",
                is_customized=ci.is_customized,
                quantity=ci.quantity,
                unit_price=calc["unit_price"],
                total_price=calc["total_price"],
                cost_unit_snapshot=float(prod.cost_price or 0.0),
                selected_options_json=ci.selected_options_json,
                pricing_snapshot_json=json.dumps(calc, ensure_ascii=False),
                immutable_config_snapshot_json=json.dumps(snap_cfg, ensure_ascii=False),
                artwork_status="pending" if ci.is_customized else "approved",
            )
        )

    if order.coupon_code:
        c_row = db.query(Coupon).filter(Coupon.code == order.coupon_code).first()
        if c_row:
            c_row.used_count = int(c_row.used_count or 0) + 1

    # Cria transação Pix / Mercado Pago (sem nunca armazenar dados de cartão)
    ext_id = f"TX-{order_number}-{uuid4().hex[:6].upper()}"
    idem_key = f"checkout_{order.id}_{ext_id}"
    pix_code = f"00020126580014BR.GOV.BCB.PIX0136{ext_id}5204000053039865406{order.total_amount:.2f}5802BR5920EDITORGRAFICA ATEL6009SAO PAULO62070503***6304"
    mp_token = os.getenv("MP_ACCESS_TOKEN", "").strip()
    checkout_url = f"/api/payments/mercadopago/redirect/{ext_id}" if payload.payment_method == "mercadopago" else ""

    tx = PaymentTransaction(
        order_id=order.id,
        provider=payload.payment_method,
        external_id=ext_id,
        idempotency_key=idem_key,
        status="pending",
        amount=order.total_amount,
        qr_code_payload=pix_code if payload.payment_method == "pix" else "",
        checkout_url=checkout_url,
        raw_payload_json=json.dumps({"mp_configured": bool(mp_token), "method": payload.payment_method}),
    )
    db.add(tx)
    _record_order_status(db, order, "aguardando_pagamento", auth.user.id, "Pedido criado via checkout.")
    create_notification_once(
        db,
        auth.user.id,
        "order_created",
        f"Pedido {order.order_number} registrado",
        f"Total R$ {order.total_amount:.2f} via {payload.payment_method.upper()}. Aguardando confirmação de pagamento.",
        dedup_key=f"order_created_{order.id}",
    )

    # Limpa carrinho
    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
    cart.coupon_code = ""
    log_audit(db, "order.created", "order", order.id, {"order_number": order.order_number, "total": order.total_amount}, auth, request)
    db.commit()
    db.refresh(order)

    return {
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "payment_status": order.payment_status,
            "payment_method": order.payment_method,
            "total_amount": order.total_amount,
        },
        "payment": {
            "external_id": tx.external_id,
            "provider": tx.provider,
            "status": tx.status,
            "amount": tx.amount,
            "qr_code_payload": tx.qr_code_payload,
            "checkout_url": tx.checkout_url,
        },
    }


@router.post("/webhooks/payment")
async def payment_webhook(
    request: Request,
    x_webhook_signature: str = Header("", alias="X-Webhook-Signature"),
    db: Session = Depends(get_db),
):
    """Recebe confirmações assinadas de Pix / Mercado Pago com idempotência estrita."""
    raw_body = await request.body()
    if not verify_webhook_signature(raw_body, x_webhook_signature):
        raise HTTPException(status_code=401, detail="Assinatura de webhook inválida.")

    try:
        data = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="JSON inválido.") from exc

    external_id = str(data.get("external_id") or "").strip()
    new_status = str(data.get("status") or "").strip().lower()
    event_id = str(data.get("event_id") or f"{external_id}:{new_status}").strip()

    if new_status not in ("pending", "approved", "refused", "cancelled", "refunded"):
        raise HTTPException(status_code=400, detail="Status de pagamento inválido.")

    tx = db.query(PaymentTransaction).filter(PaymentTransaction.external_id == external_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transação não encontrada.")

    # Proteção contra notificações duplicadas / idempotência
    raw_prev = _jload(tx.raw_payload_json, {})
    processed_events = set(raw_prev.get("processed_events") or [])
    if event_id in processed_events or (tx.status == new_status and new_status != "pending"):
        return {"ok": True, "idempotent": True, "status": tx.status}

    processed_events.add(event_id)
    raw_prev["processed_events"] = list(processed_events)
    tx.raw_payload_json = json.dumps(raw_prev, ensure_ascii=False)
    tx.status = new_status

    order = db.query(Order).filter(Order.id == tx.order_id).first()
    if order:
        order.payment_status = new_status
        if new_status == "approved":
            order.paid_at = datetime.now(timezone.utc)
            has_custom = db.query(OrderItem).filter(OrderItem.order_id == order.id, OrderItem.is_customized == True).count() > 0
            next_st = "em_personalizacao" if has_custom else "liberado_producao"
            _record_order_status(db, order, next_st, None, f"Pagamento aprovado via {tx.provider} ({external_id}).")
            create_notification_once(
                db,
                order.user_id,
                "payment_approved",
                f"Pagamento aprovado — Pedido {order.order_number}",
                f"Seu pagamento de R$ {order.total_amount:.2f} foi confirmado!",
                dedup_key=f"pay_ok_{order.id}_{tx.id}",
            )
        elif new_status in ("refused", "cancelled", "refunded"):
            if new_status == "cancelled":
                _record_order_status(db, order, "cancelado", None, f"Pagamento {new_status} ({external_id}).")
            create_notification_once(
                db,
                order.user_id,
                f"payment_{new_status}",
                f"Atualização de pagamento — Pedido {order.order_number}",
                f"Status do pagamento atualizado para: {new_status}.",
                dedup_key=f"pay_{new_status}_{order.id}_{event_id}",
            )

    log_audit(db, "payment.webhook", "payment_transaction", tx.id, {"external_id": external_id, "status": new_status}, None, request)
    db.commit()
    return {"ok": True, "idempotent": False, "order_id": tx.order_id, "payment_status": tx.status}


@router.post("/admin/payments/{external_id}/sandbox-confirm")
def admin_sandbox_confirm_payment(
    external_id: str,
    status: str = Query("approved", pattern="^(approved|refused|cancelled|refunded)$"),
    auth: AuthContext = Depends(require_permission("payments", "edit")),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Permite que administradores testem a confirmação de pagamento em ambiente sandbox."""
    tx = db.query(PaymentTransaction).filter(PaymentTransaction.external_id == external_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transação não encontrada.")
    order = db.query(Order).filter(Order.id == tx.order_id).first()
    tx.status = status
    if order:
        order.payment_status = status
        if status == "approved":
            order.paid_at = datetime.now(timezone.utc)
            has_custom = db.query(OrderItem).filter(OrderItem.order_id == order.id, OrderItem.is_customized == True).count() > 0
            _record_order_status(db, order, "em_personalizacao" if has_custom else "liberado_producao", auth.user.id, "Confirmação sandbox pelo administrador.")
            create_notification_once(
                db,
                order.user_id,
                "payment_approved",
                f"Pagamento confirmado — Pedido {order.order_number}",
                f"Pagamento de R$ {order.total_amount:.2f} confirmado.",
                dedup_key=f"pay_ok_{order.id}_{tx.id}",
            )
    log_audit(db, "payment.sandbox_confirm", "payment_transaction", tx.id, {"status": status}, auth, request)
    db.commit()
    return {"ok": True, "order_status": order.status if order else "", "payment_status": status}


# ==================== ÁREA DO CLIENTE & APROVAÇÃO DE ARTE ====================


def _serialize_order_full(db: Session, o: Order) -> dict[str, Any]:
    cust = db.query(User).filter(User.id == o.user_id).first()
    items = db.query(OrderItem).filter(OrderItem.order_id == o.id).order_by(OrderItem.id.asc()).all()
    hist = db.query(OrderStatusHistory).filter(OrderStatusHistory.order_id == o.id).order_by(OrderStatusHistory.id.asc()).all()
    txs = db.query(PaymentTransaction).filter(PaymentTransaction.order_id == o.id).order_by(PaymentTransaction.id.desc()).all()
    approvals = db.query(ArtworkApproval).filter(ArtworkApproval.order_id == o.id).order_by(ArtworkApproval.id.desc()).all()
    editor = db.query(User).filter(User.id == o.assigned_editor_id).first() if o.assigned_editor_id else None

    return {
        "id": o.id,
        "order_number": o.order_number,
        "user_id": o.user_id,
        "customer_name": cust.name if cust else "",
        "customer_email": cust.email if cust else "",
        "status": o.status,
        "status_label": ORDER_STATUS_LABELS.get(o.status, o.status),
        "subtotal": o.subtotal,
        "discount_total": o.discount_total,
        "shipping_total": o.shipping_total,
        "total_amount": o.total_amount,
        "coupon_code": o.coupon_code,
        "shipping_address": _jload(o.shipping_address_json, {}),
        "payment_method": o.payment_method,
        "payment_status": o.payment_status,
        "assigned_editor_id": o.assigned_editor_id,
        "assigned_editor_name": editor.name if editor else "",
        "priority": o.priority,
        "customer_notes": o.customer_notes,
        "internal_notes": o.internal_notes,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "items": [
            {
                "id": it.id,
                "product_id": it.product_id,
                "product_name": it.product_name,
                "variation_name": it.variation_name,
                "sku": it.sku,
                "is_customized": it.is_customized,
                "project_id": it.project_id,
                "project_version": it.project_version,
                "quantity": it.quantity,
                "unit_price": it.unit_price,
                "total_price": it.total_price,
                "selected_options": _jload(it.selected_options_json, {}),
                "pricing_snapshot": _jload(it.pricing_snapshot_json, {}),
                "preview_file_id": it.preview_file_id,
                "final_file_id": it.final_file_id,
                "preflight_report": _jload(it.preflight_report_json, {}),
                "artwork_status": it.artwork_status,
                "approved_version": it.approved_version,
            }
            for it in items
        ],
        "timeline": [
            {
                "from_status": h.from_status,
                "to_status": h.to_status,
                "to_label": ORDER_STATUS_LABELS.get(h.to_status, h.to_status),
                "note": h.note,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in hist
        ],
        "transactions": [
            {
                "id": t.id,
                "provider": t.provider,
                "external_id": t.external_id,
                "status": t.status,
                "amount": t.amount,
                "qr_code_payload": t.qr_code_payload,
                "checkout_url": t.checkout_url,
            }
            for t in txs
        ],
        "approvals": [
            {
                "id": a.id,
                "order_item_id": a.order_item_id,
                "project_version": a.project_version,
                "decision": a.decision,
                "comments": a.comments,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in approvals
        ],
    }


@router.get("/account/dashboard")
def account_dashboard(auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.user_id == auth.user.id).order_by(Order.id.desc()).all()
    projects = db.query(Project).filter(Project.owner_id == auth.user.id).order_by(Project.updated_at.desc()).all()
    notifs = db.query(Notification).filter(Notification.user_id == auth.user.id).order_by(Notification.id.desc()).limit(10).all()

    in_progress = [o for o in orders if o.status not in ("entregue", "cancelado", "finalizado")]
    completed = [o for o in orders if o.status in ("finalizado", "entregue")]
    unfinished_projs = [p for p in projects if p.status == "draft"]

    return {
        "kpis": {
            "total_orders": len(orders),
            "orders_in_progress": len(in_progress),
            "orders_completed": len(completed),
            "unfinished_projects": len(unfinished_projs),
            "total_projects": len(projects),
        },
        "recent_orders": [_serialize_order_full(db, o) for o in orders[:5]],
        "recent_projects": [
            {"id": p.id, "name": p.name, "status": p.status, "version": p.version, "page_count": p.page_count, "product_id": p.product_id, "updated_at": p.updated_at.isoformat() if p.updated_at else None}
            for p in projects[:6]
        ],
        "notifications": [
            {"id": n.id, "title": n.title, "message": n.message, "is_read": n.is_read, "created_at": n.created_at.isoformat()}
            for n in notifs
        ],
    }


@router.get("/account/orders")
def list_my_orders(auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.user_id == auth.user.id).order_by(Order.id.desc()).all()
    return {"orders": [_serialize_order_full(db, o) for o in orders]}


@router.get("/account/orders/{order_id}")
def get_my_order(order_id: int, auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    ensure_owner_or_staff(auth, order.user_id, "orders", "read")
    return {"order": _serialize_order_full(db, order)}


@router.post("/account/orders/{order_id}/items/{item_id}/artwork-decision")
def decide_artwork(
    order_id: int,
    item_id: int,
    payload: ArtworkDecisionRequest,
    auth: AuthContext = Depends(get_current_auth),
    request: Request = None,
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    ensure_owner_or_staff(auth, order.user_id, "artworks", "approve")
    item = db.query(OrderItem).filter(OrderItem.id == item_id, OrderItem.order_id == order.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item do pedido não encontrado.")

    ver = int(item.project_version or 1)
    db.add(
        ArtworkApproval(
            order_id=order.id,
            order_item_id=item.id,
            project_version=ver,
            decision=payload.decision,
            comments=payload.comments,
            decided_by_id=auth.user.id,
            preview_file_id=item.preview_file_id,
        )
    )
    item.artwork_status = payload.decision
    if payload.decision == "approved":
        item.approved_version = ver
        # Verifica se todos itens customizados do pedido estão aprovados na versão corrente
        all_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        if all((not it.is_customized) or (it.artwork_status == "approved" and it.approved_version == (it.project_version or 1)) for it in all_items):
            _record_order_status(db, order, "aprovado_cliente", auth.user.id, f"Arte v{ver} aprovada pelo cliente.")
        create_notification_once(
            db,
            order.user_id,
            "artwork_approved",
            f"Arte aprovada — Pedido {order.order_number}",
            f"Você aprovou a versão v{ver} de '{item.product_name}'.",
            dedup_key=f"art_app_{order.id}_{item.id}_v{ver}",
        )
    else:
        item.approved_version = None
        _record_order_status(db, order, "aguardando_correcao", auth.user.id, f"Alterações solicitadas: {payload.comments}")
        create_notification_once(
            db,
            order.user_id,
            "artwork_changes",
            f"Ajuste solicitado — Pedido {order.order_number}",
            f"Sua solicitação para '{item.product_name}' foi registrada: {payload.comments}",
            dedup_key=f"art_chg_{order.id}_{item.id}_{uuid4().hex[:6]}",
        )

    log_audit(db, f"artwork.{payload.decision}", "order_item", item.id, {"version": ver}, auth, request)
    db.commit()
    return {"ok": True, "order": _serialize_order_full(db, order)}


@router.get("/account/projects")
def list_my_projects(auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    rows = db.query(Project).filter(Project.owner_id == auth.user.id).order_by(Project.updated_at.desc()).all()
    return {
        "projects": [
            {
                "id": p.id, "name": p.name, "year": p.year, "format_name": p.format_name,
                "page_count": p.page_count, "version": p.version, "status": p.status,
                "product_id": p.product_id, "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in rows
        ]
    }


@router.get("/account/files")
def list_my_files(auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    files = db.query(MediaFile).filter(MediaFile.owner_id == auth.user.id).order_by(MediaFile.id.desc()).all()
    return {
        "files": [
            {
                "id": f.id, "original_name": f.original_name, "folder": f.folder, "category": f.category,
                "mime_type": f.mime_type, "size_bytes": f.size_bytes, "order_id": f.order_id,
                "version": f.version, "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in files
        ]
    }


@router.get("/account/addresses")
def list_my_addresses(auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    addrs = db.query(CustomerAddress).filter(CustomerAddress.user_id == auth.user.id).all()
    return {
        "addresses": [
            {
                "id": a.id, "label": a.label, "recipient_name": a.recipient_name,
                "street": a.street, "number": a.number, "complement": a.complement,
                "neighborhood": a.neighborhood, "city": a.city, "state": a.state,
                "zip_code": a.zip_code, "is_default": a.is_default,
            }
            for a in addrs
        ]
    }


@router.post("/account/addresses", status_code=201)
def create_my_address(payload: AddressPayload, auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    if payload.is_default:
        db.query(CustomerAddress).filter(CustomerAddress.user_id == auth.user.id).update({"is_default": False})
    a = CustomerAddress(user_id=auth.user.id, **payload.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": a.id, **payload.model_dump()}


@router.get("/account/favorites")
def list_favorites(auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    favs = db.query(Favorite).filter(Favorite.user_id == auth.user.id).all()
    prods = []
    for f in favs:
        p = db.query(Product).filter(Product.id == f.product_id, Product.status == "active").first()
        if p:
            prods.append(_serialize_product(db, p, include_variations=False))
    return {"favorites": prods}


@router.post("/account/favorites/{product_id}")
def toggle_favorite(product_id: int, auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    existing = db.query(Favorite).filter(Favorite.user_id == auth.user.id, Favorite.product_id == product_id).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"favorited": False}
    db.add(Favorite(user_id=auth.user.id, product_id=product_id))
    db.commit()
    return {"favorited": True}


@router.get("/account/notifications")
def list_notifications(auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    rows = db.query(Notification).filter(Notification.user_id == auth.user.id).order_by(Notification.id.desc()).limit(40).all()
    return {
        "notifications": [
            {"id": n.id, "title": n.title, "message": n.message, "is_read": n.is_read, "event_key": n.event_key, "created_at": n.created_at.isoformat()}
            for n in rows
        ]
    }


@router.post("/account/notifications/read-all")
def mark_notifications_read(auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.user_id == auth.user.id, Notification.is_read == False).update({"is_read": True})
    db.commit()
    return {"ok": True}


@router.get("/account/support")
def list_my_tickets(auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    rows = db.query(SupportTicket).filter(SupportTicket.user_id == auth.user.id).order_by(SupportTicket.id.desc()).all()
    return {
        "tickets": [
            {"id": t.id, "subject": t.subject, "message": t.message, "status": t.status, "admin_reply": t.admin_reply, "order_id": t.order_id, "created_at": t.created_at.isoformat()}
            for t in rows
        ]
    }


@router.post("/account/support", status_code=201)
def create_support_ticket(payload: SupportTicketCreate, auth: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    t = SupportTicket(user_id=auth.user.id, order_id=payload.order_id, subject=payload.subject, message=payload.message)
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id, "status": t.status}


# ==================== ARQUIVOS PRIVADOS PROTEGIDOS ====================


@router.get("/files/{file_id}/download")
def download_protected_file(
    file_id: int,
    inline: bool = Query(False),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    mf = db.query(MediaFile).filter(MediaFile.id == file_id).first()
    if not mf:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    if mf.is_private:
        ensure_owner_or_staff(auth, mf.owner_id, "files", "files")
        if mf.folder == "final_print" and not auth.is_staff:
            # Verifica se o pedido está pago ou se o produto libera download final ao cliente
            if mf.order_id:
                ord_obj = db.query(Order).filter(Order.id == mf.order_id).first()
                if not ord_obj or ord_obj.payment_status != "approved":
                    raise HTTPException(status_code=403, detail="Arquivo final disponível somente após pagamento aprovado.")
            if mf.project_id:
                proj = db.query(Project).filter(Project.id == mf.project_id).first()
                if proj and proj.product_id:
                    prod = db.query(Product).filter(Product.id == proj.product_id).first()
                    tools = normalize_editor_tools(_jload(prod.allowed_tools_json, {}) if prod else {})
                    # Cliente pode baixar final se permitido no produto OU após aprovação/conclusão
                    if not tools.get("download_final"):
                        item = db.query(OrderItem).filter(OrderItem.final_file_id == mf.id).first()
                        if not item or item.artwork_status != "approved":
                            raise HTTPException(status_code=403, detail="Download do arquivo final restrito à produção ou após aprovação da arte.")

    abs_path = (BASE_DIR / mf.stored_path).resolve()
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo físico indisponível.")
    disp = "inline" if inline else "attachment"
    return FileResponse(
        path=str(abs_path),
        media_type=mf.mime_type,
        headers={"Content-Disposition": f'{disp}; filename="{mf.original_name}"'},
    )


# ==================== PRODUÇÃO GRÁFICA & FILA ====================


@router.get("/production/queue")
def list_production_queue(
    status_filter: str = "",
    auth: AuthContext = Depends(require_permission("production", "read")),
    db: Session = Depends(get_db),
):
    q = db.query(Order).order_by(Order.priority.desc(), Order.id.desc())
    if status_filter:
        q = q.filter(Order.status == status_filter)
    orders = q.all()
    editors = (
        db.query(User)
        .join(Role, User.role_id == Role.id)
        .filter(Role.slug != "customer", User.is_active == True)
        .all()
    )
    return {
        "orders": [_serialize_order_full(db, o) for o in orders],
        "status_options": ORDER_STATUS_LABELS,
        "editors": [{"id": e.id, "name": e.name, "email": e.email} for e in editors],
    }


@router.post("/production/orders/{order_id}/assign")
def assign_order_editor(
    order_id: int,
    payload: OrderAssignRequest,
    auth: AuthContext = Depends(require_permission("production", "edit")),
    request: Request = None,
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    ed = db.query(User).filter(User.id == payload.editor_user_id).first()
    if not ed:
        raise HTTPException(status_code=404, detail="Editor não encontrado.")
    order.assigned_editor_id = ed.id
    log_audit(db, "production.assign", "order", order.id, {"editor_id": ed.id}, auth, request)
    db.commit()
    return {"ok": True, "order": _serialize_order_full(db, order)}


@router.post("/production/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdateRequest,
    auth: AuthContext = Depends(require_permission("orders", "edit")),
    request: Request = None,
    db: Session = Depends(get_db),
):
    if payload.status not in ORDER_STATUS_LABELS:
        raise HTTPException(status_code=400, detail="Status inválido.")
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    if payload.priority:
        order.priority = payload.priority
    if payload.internal_notes is not None:
        order.internal_notes = payload.internal_notes
    _record_order_status(db, order, payload.status, auth.user.id, payload.note or ORDER_STATUS_LABELS[payload.status])
    create_notification_once(
        db,
        order.user_id,
        f"order_status_{payload.status}",
        f"Pedido {order.order_number}: {ORDER_STATUS_LABELS[payload.status]}",
        payload.note or f"Seu pedido avançou para a etapa: {ORDER_STATUS_LABELS[payload.status]}.",
        dedup_key=f"ord_st_{order.id}_{payload.status}_{uuid4().hex[:5]}",
    )
    log_audit(db, "order.status_change", "order", order.id, {"to_status": payload.status}, auth, request)
    db.commit()
    return {"ok": True, "order": _serialize_order_full(db, order)}


@router.post("/production/orders/{order_id}/items/{item_id}/generate-files")
async def production_generate_files(
    order_id: int,
    item_id: int,
    background_tasks: BackgroundTasks,
    include_bleed: bool = Query(True),
    include_crop_marks: bool = Query(True),
    async_bg: bool = Query(False),
    auth: AuthContext = Depends(require_permission("production", "export")),
    request: Request = None,
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    item = db.query(OrderItem).filter(OrderItem.id == item_id, OrderItem.order_id == order_id).first()
    if not order or not item:
        raise HTTPException(status_code=404, detail="Pedido ou item não encontrado.")

    log_audit(db, "production.generate_files", "order_item", item.id, {"async": async_bg}, auth, request)
    db.commit()

    if async_bg:
        background_tasks.add_task(_bg_generate_order_files, order_id, item_id, include_bleed, include_crop_marks, auth.user.id)
        return {"queued": True, "order_id": order_id, "item_id": item_id}

    res = await run_in_threadpool(_generate_item_pdf_files_sync, db, order, item, include_bleed, include_crop_marks, auth.user.id)
    return res


# ==================== ADMINISTRAÇÃO, RBAC, RELATÓRIOS & MÍDIA ====================


@router.get("/admin/dashboard")
def admin_dashboard(
    days: int = Query(30, ge=1, le=3650),
    auth: AuthContext = Depends(require_permission("reports", "read")),
    db: Session = Depends(get_db),
):
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    all_orders = db.query(Order).all()
    period_orders = [o for o in all_orders if o.created_at and (o.created_at if o.created_at.tzinfo else o.created_at.replace(tzinfo=timezone.utc)) >= cutoff]

    paid_orders = [o for o in period_orders if o.payment_status == "approved"]
    revenue = round(sum(float(o.total_amount) for o in paid_orders), 2)
    pending_orders = [o for o in all_orders if o.status in ("aguardando_pagamento", "aguardando_aprovacao", "aguardando_correcao")]
    in_prod = [o for o in all_orders if o.status in ("liberado_producao", "em_producao", "em_pre_impressao")]
    completed = [o for o in all_orders if o.status in ("finalizado", "entregue")]
    customers_count = db.query(User).join(Role, User.role_id == Role.id).filter(Role.slug == "customer").count()

    top_products = (
        db.query(Product)
        .filter(Product.status == "active")
        .order_by(Product.sales_count.desc())
        .limit(5)
        .all()
    )

    # Rentabilidade estimada por produto com custo cadastrado
    all_items = db.query(OrderItem).all()
    profit_by_prod: dict[str, dict[str, float]] = {}
    for it in all_items:
        ent = profit_by_prod.setdefault(it.product_name, {"revenue": 0.0, "cost": 0.0, "profit": 0.0, "qty": 0})
        ent["revenue"] += float(it.total_price)
        ent["cost"] += float(it.cost_unit_snapshot or 0.0) * int(it.quantity)
        ent["profit"] = round(ent["revenue"] - ent["cost"], 2)
        ent["qty"] += int(it.quantity)

    # Receita por status
    status_counts: dict[str, int] = {}
    for o in all_orders:
        status_counts[o.status] = status_counts.get(o.status, 0) + 1

    return {
        "kpis": {
            "revenue": revenue,
            "total_orders": len(period_orders),
            "pending_orders": len(pending_orders),
            "in_production": len(in_prod),
            "completed_orders": len(completed),
            "customers_count": customers_count,
            "conversion_rate": round((len(paid_orders) / len(period_orders) * 100.0), 1) if period_orders else 0.0,
        },
        "top_products": [{"id": p.id, "name": p.name, "sales_count": p.sales_count, "base_price": p.base_price} for p in top_products],
        "profitability": sorted([{"product_name": k, **v} for k, v in profit_by_prod.items()], key=lambda x: x["profit"], reverse=True)[:5],
        "status_breakdown": status_counts,
    }


@router.get("/admin/categories")
def admin_list_categories(auth: AuthContext = Depends(require_permission("categories", "read")), db: Session = Depends(get_db)):
    cats = db.query(Category).order_by(Category.sort_order.asc()).all()
    return {"categories": [{"id": c.id, "name": c.name, "slug": c.slug, "description": c.description, "image_url": c.image_url, "sort_order": c.sort_order, "is_active": c.is_active} for c in cats]}


@router.post("/admin/categories", status_code=201)
def admin_create_category(payload: CategoryPayload, auth: AuthContext = Depends(require_permission("categories", "create")), db: Session = Depends(get_db)):
    slug = payload.slug or _slugify(payload.name)
    c = Category(name=payload.name, slug=slug, description=payload.description, image_url=payload.image_url, sort_order=payload.sort_order, is_active=payload.is_active)
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "name": c.name, "slug": c.slug}


@router.put("/admin/categories/{cat_id}")
def admin_update_category(cat_id: int, payload: CategoryPayload, auth: AuthContext = Depends(require_permission("categories", "edit")), db: Session = Depends(get_db)):
    c = db.query(Category).filter(Category.id == cat_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    c.name = payload.name
    c.description = payload.description
    c.image_url = payload.image_url
    c.sort_order = payload.sort_order
    c.is_active = payload.is_active
    db.commit()
    return {"ok": True}


@router.get("/admin/products")
def admin_list_products(auth: AuthContext = Depends(require_permission("products", "read")), db: Session = Depends(get_db)):
    prods = db.query(Product).order_by(Product.id.desc()).all()
    return {"products": [_serialize_product(db, p, include_variations=True) for p in prods]}


@router.post("/admin/products", status_code=201)
def admin_create_product(payload: ProductPayload, auth: AuthContext = Depends(require_permission("products", "create")), request: Request = None, db: Session = Depends(get_db)):
    slug = payload.slug or _slugify(payload.name)
    p = Product(
        name=payload.name,
        sku=payload.sku.strip().upper(),
        slug=slug,
        category_id=payload.category_id,
        short_description=payload.short_description,
        full_description=payload.full_description,
        images_json=json.dumps(payload.images),
        mockups_json=json.dumps(payload.mockups),
        demo_file_url=payload.demo_file_url,
        base_price=payload.base_price,
        promo_price=payload.promo_price,
        cost_price=payload.cost_price,
        product_type=payload.product_type,
        status=payload.status,
        is_available=payload.is_available,
        stock_qty=payload.stock_qty,
        is_featured=payload.is_featured,
        commercial_tag=payload.commercial_tag,
        is_customizable=payload.is_customizable,
        template_id=payload.template_id,
        allowed_tools_json=json.dumps(normalize_editor_tools(payload.allowed_tools)),
        pricing_rules_json=json.dumps(payload.pricing_rules, ensure_ascii=False),
        specs_json=json.dumps(payload.specs, ensure_ascii=False),
    )
    db.add(p)
    db.flush()
    for idx, v in enumerate(payload.variations):
        db.add(ProductVariation(product_id=p.id, sort_order=idx, **v.model_dump()))
    log_audit(db, "product.create", "product", p.id, {"sku": p.sku}, auth, request)
    db.commit()
    return {"product": _serialize_product(db, p)}


@router.put("/admin/products/{product_id}")
def admin_update_product(product_id: int, payload: ProductPayload, auth: AuthContext = Depends(require_permission("products", "edit")), request: Request = None, db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    p.name = payload.name
    p.sku = payload.sku.strip().upper()
    p.category_id = payload.category_id
    p.short_description = payload.short_description
    p.full_description = payload.full_description
    if payload.images:
        p.images_json = json.dumps(payload.images)
    if payload.mockups:
        p.mockups_json = json.dumps(payload.mockups)
    p.base_price = payload.base_price
    p.promo_price = payload.promo_price
    p.cost_price = payload.cost_price
    p.product_type = payload.product_type
    p.status = payload.status
    p.is_available = payload.is_available
    p.stock_qty = payload.stock_qty
    p.is_featured = payload.is_featured
    p.commercial_tag = payload.commercial_tag
    p.is_customizable = payload.is_customizable
    p.template_id = payload.template_id
    if payload.allowed_tools:
        p.allowed_tools_json = json.dumps(normalize_editor_tools(payload.allowed_tools))
    if payload.pricing_rules:
        p.pricing_rules_json = json.dumps(payload.pricing_rules, ensure_ascii=False)
    if payload.specs:
        p.specs_json = json.dumps(payload.specs, ensure_ascii=False)
    if payload.variations:
        db.query(ProductVariation).filter(ProductVariation.product_id == p.id).delete()
        for idx, v in enumerate(payload.variations):
            db.add(ProductVariation(product_id=p.id, sort_order=idx, **v.model_dump()))
    log_audit(db, "product.update", "product", p.id, {"sku": p.sku}, auth, request)
    db.commit()
    return {"product": _serialize_product(db, p)}


@router.delete("/admin/products/{product_id}")
def admin_delete_product(product_id: int, auth: AuthContext = Depends(require_permission("products", "delete")), db: Session = Depends(get_db)):
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    p.status = "archived"
    p.is_available = False
    db.commit()
    return {"archived": True}


# ---------------- BIBLIOTECA DE MODELOS VERSIONADOS ----------------


@router.get("/admin/templates")
def admin_list_templates(auth: AuthContext = Depends(require_permission("templates", "read")), db: Session = Depends(get_db)):
    tpls = db.query(GraphicTemplate).order_by(GraphicTemplate.id.desc()).all()
    out = []
    for t in tpls:
        vers = db.query(GraphicTemplateVersion).filter(GraphicTemplateVersion.template_id == t.id).order_by(GraphicTemplateVersion.version_number.desc()).all()
        out.append(
            {
                "id": t.id, "name": t.name, "slug": t.slug, "description": t.description,
                "category_slug": t.category_slug, "base_layout_mode": t.base_layout_mode,
                "status": t.status, "current_version": t.current_version,
                "allowed_tools": normalize_editor_tools(_jload(t.allowed_tools_json, {})),
                "versions": [
                    {"version_number": v.version_number, "changelog": v.changelog, "is_published": v.is_published, "created_at": v.created_at.isoformat()}
                    for v in vers
                ],
            }
        )
    return {"templates": out}


@router.post("/admin/templates", status_code=201)
def admin_create_template(payload: TemplatePayload, auth: AuthContext = Depends(require_permission("templates", "create")), db: Session = Depends(get_db)):
    slug = payload.slug or _slugify(payload.name)
    tools = normalize_editor_tools(payload.allowed_tools)
    cfg = ProjectConfig.model_validate(payload.config).model_dump()
    t = GraphicTemplate(
        name=payload.name, slug=slug, description=payload.description,
        category_slug=payload.category_slug, base_layout_mode=payload.base_layout_mode,
        status=payload.status, current_version=1,
        allowed_tools_json=json.dumps(tools), created_by_id=auth.user.id,
    )
    db.add(t)
    db.flush()
    db.add(
        GraphicTemplateVersion(
            template_id=t.id, version_number=1, config_json=json.dumps(cfg, ensure_ascii=False),
            allowed_tools_json=json.dumps(tools), changelog=payload.changelog,
            is_published=(payload.status == "published"), created_by_id=auth.user.id,
        )
    )
    db.commit()
    return {"id": t.id, "name": t.name, "current_version": 1}


@router.post("/admin/templates/{template_id}/versions", status_code=201)
def admin_create_template_version(
    template_id: int,
    payload: TemplatePayload,
    auth: AuthContext = Depends(require_permission("templates", "edit")),
    db: Session = Depends(get_db),
):
    """Cria nova versão imutável sem alterar projetos ou pedidos existentes."""
    t = db.query(GraphicTemplate).filter(GraphicTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    next_ver = int(t.current_version or 1) + 1
    tools = normalize_editor_tools(payload.allowed_tools)
    cfg = ProjectConfig.model_validate(payload.config).model_dump()
    t.name = payload.name
    t.description = payload.description
    t.current_version = next_ver
    t.allowed_tools_json = json.dumps(tools)
    t.status = payload.status
    db.add(
        GraphicTemplateVersion(
            template_id=t.id, version_number=next_ver, config_json=json.dumps(cfg, ensure_ascii=False),
            allowed_tools_json=json.dumps(tools), changelog=payload.changelog,
            is_published=(payload.status == "published"), created_by_id=auth.user.id,
        )
    )
    db.commit()
    return {"id": t.id, "current_version": next_ver}


@router.post("/admin/templates/{template_id}/status")
def admin_set_template_status(
    template_id: int,
    status: str = Query(..., pattern="^(draft|published|unpublished|archived)$"),
    auth: AuthContext = Depends(require_permission("templates", "publish")),
    db: Session = Depends(get_db),
):
    t = db.query(GraphicTemplate).filter(GraphicTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    t.status = status
    latest = db.query(GraphicTemplateVersion).filter(GraphicTemplateVersion.template_id == t.id, GraphicTemplateVersion.version_number == t.current_version).first()
    if latest:
        latest.is_published = (status == "published")
    db.commit()
    return {"id": t.id, "status": t.status}


@router.post("/admin/templates/{template_id}/duplicate", status_code=201)
def admin_duplicate_template(template_id: int, auth: AuthContext = Depends(require_permission("templates", "create")), db: Session = Depends(get_db)):
    t = db.query(GraphicTemplate).filter(GraphicTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    latest = db.query(GraphicTemplateVersion).filter(GraphicTemplateVersion.template_id == t.id, GraphicTemplateVersion.version_number == t.current_version).first()
    dup = GraphicTemplate(
        name=f"{t.name} (Cópia)", slug=f"{t.slug}-copia-{uuid4().hex[:4]}",
        description=t.description, category_slug=t.category_slug, base_layout_mode=t.base_layout_mode,
        status="draft", current_version=1, allowed_tools_json=t.allowed_tools_json, created_by_id=auth.user.id,
    )
    db.add(dup)
    db.flush()
    db.add(
        GraphicTemplateVersion(
            template_id=dup.id, version_number=1, config_json=latest.config_json if latest else "{}",
            allowed_tools_json=t.allowed_tools_json, changelog="Duplicado", is_published=False, created_by_id=auth.user.id,
        )
    )
    db.commit()
    return {"id": dup.id, "name": dup.name}


# ---------------- USUÁRIOS & MATRIZ RBAC ----------------


@router.get("/admin/roles")
def admin_list_roles(auth: AuthContext = Depends(require_permission("permissions", "read")), db: Session = Depends(get_db)):
    roles = db.query(Role).order_by(Role.id.asc()).all()
    return {
        "modules": RBAC_MODULES,
        "editor_tool_labels": EDITOR_TOOL_LABELS,
        "roles": [
            {
                "id": r.id, "slug": r.slug, "name": r.name, "description": r.description,
                "is_system": r.is_system, "permissions": _jload(r.permissions_json, {}),
            }
            for r in roles
        ],
    }


@router.post("/admin/roles", status_code=201)
def admin_create_role(payload: RolePayload, auth: AuthContext = Depends(require_permission("permissions", "create")), request: Request = None, db: Session = Depends(get_db)):
    slug = payload.slug or _slugify(payload.name)
    r = Role(slug=slug, name=payload.name, description=payload.description, is_system=False, permissions_json=json.dumps(payload.permissions))
    db.add(r)
    db.flush()
    log_audit(db, "rbac.role_create", "role", r.id, {"slug": slug}, auth, request)
    db.commit()
    return {"id": r.id, "slug": r.slug}


@router.put("/admin/roles/{role_id}")
def admin_update_role(role_id: int, payload: RolePayload, auth: AuthContext = Depends(require_permission("permissions", "edit")), request: Request = None, db: Session = Depends(get_db)):
    r = db.query(Role).filter(Role.id == role_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    old_perms = _jload(r.permissions_json, {})
    r.name = payload.name
    r.description = payload.description
    r.permissions_json = json.dumps(payload.permissions)
    log_audit(db, "rbac.role_update", "role", r.id, {"slug": r.slug, "old": old_perms, "new": payload.permissions}, auth, request)
    db.commit()
    return {"ok": True}


@router.post("/admin/roles/{role_id}/clone", status_code=201)
def admin_clone_role(role_id: int, new_name: str = Query(...), auth: AuthContext = Depends(require_permission("permissions", "create")), request: Request = None, db: Session = Depends(get_db)):
    r = db.query(Role).filter(Role.id == role_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    clone = Role(slug=f"{_slugify(new_name)}-{uuid4().hex[:4]}", name=new_name, description=f"Clonado de {r.name}", is_system=False, permissions_json=r.permissions_json)
    db.add(clone)
    db.flush()
    log_audit(db, "rbac.role_clone", "role", clone.id, {"from_role": r.id}, auth, request)
    db.commit()
    return {"id": clone.id, "slug": clone.slug, "name": clone.name}


@router.get("/admin/users")
def admin_list_users(auth: AuthContext = Depends(require_permission("users", "read")), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id.asc()).all()
    roles_by_id = {r.id: r for r in db.query(Role).all()}
    return {"users": [_serialize_user(u, roles_by_id.get(u.role_id)) for u in users]}


@router.post("/admin/users", status_code=201)
def admin_create_user(payload: UserAdminCreatePayload, auth: AuthContext = Depends(require_permission("users", "create")), request: Request = None, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="E-mail já existe.")
    u = User(name=payload.name, email=email, password_hash=hash_password(payload.password), phone=payload.phone, role_id=payload.role_id, is_active=True)
    db.add(u)
    db.flush()
    log_audit(db, "user.create", "user", u.id, {"email": email, "role_id": payload.role_id}, auth, request)
    db.commit()
    role = db.query(Role).filter(Role.id == u.role_id).first()
    return {"user": _serialize_user(u, role)}


@router.put("/admin/users/{user_id}")
def admin_update_user(user_id: int, payload: UserAdminUpdatePayload, auth: AuthContext = Depends(require_permission("users", "edit")), request: Request = None, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if payload.name is not None:
        u.name = payload.name
    if payload.phone is not None:
        u.phone = payload.phone
    if payload.role_id is not None:
        u.role_id = payload.role_id
    if payload.is_active is not None:
        u.is_active = payload.is_active
    if payload.custom_permissions is not None:
        if not auth.can("permissions", "edit"):
            raise HTTPException(status_code=403, detail="Permissão 'permissions:edit' necessária para alterar overrides.")
        u.custom_permissions_json = json.dumps(payload.custom_permissions)
    log_audit(db, "user.update", "user", u.id, payload.model_dump(exclude_none=True), auth, request)
    db.commit()
    role = db.query(Role).filter(Role.id == u.role_id).first()
    return {"user": _serialize_user(u, role)}


# ---------------- CUPONS, CONFIGURAÇÕES, MÍDIA, SUPORTE, AUDITORIA & RELATÓRIOS ----------------


@router.get("/admin/coupons")
def admin_list_coupons(auth: AuthContext = Depends(require_permission("coupons", "read")), db: Session = Depends(get_db)):
    rows = db.query(Coupon).order_by(Coupon.id.desc()).all()
    return {
        "coupons": [
            {
                "id": c.id, "code": c.code, "description": c.description, "discount_type": c.discount_type,
                "discount_value": c.discount_value, "min_order_value": c.min_order_value, "min_quantity": c.min_quantity,
                "max_uses": c.max_uses, "used_count": c.used_count, "is_active": c.is_active,
            }
            for c in rows
        ]
    }


@router.post("/admin/coupons", status_code=201)
def admin_create_coupon(payload: CouponPayload, auth: AuthContext = Depends(require_permission("coupons", "create")), db: Session = Depends(get_db)):
    c = Coupon(
        code=payload.code.strip().upper(),
        description=payload.description,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        min_order_value=payload.min_order_value,
        min_quantity=payload.min_quantity,
        max_uses=payload.max_uses,
        max_uses_per_user=payload.max_uses_per_user,
        eligible_product_ids_json=json.dumps(payload.eligible_product_ids),
        eligible_category_ids_json=json.dumps(payload.eligible_category_ids),
        is_active=payload.is_active,
    )
    db.add(c)
    db.commit()
    return {"id": c.id, "code": c.code}


@router.delete("/admin/coupons/{coupon_id}")
def admin_toggle_coupon(coupon_id: int, auth: AuthContext = Depends(require_permission("coupons", "delete")), db: Session = Depends(get_db)):
    c = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cupom não encontrado.")
    c.is_active = not c.is_active
    db.commit()
    return {"id": c.id, "is_active": c.is_active}


@router.get("/admin/settings")
def admin_get_settings(auth: AuthContext = Depends(require_permission("settings", "read")), db: Session = Depends(get_db)):
    rows = db.query(StoreSetting).all()
    return {"settings": {r.key: _jload(r.value_json, {}) for r in rows}}


@router.put("/admin/settings/{key}")
def admin_update_setting(key: str, value: dict[str, Any], auth: AuthContext = Depends(require_permission("settings", "edit")), request: Request = None, db: Session = Depends(get_db)):
    row = db.query(StoreSetting).filter(StoreSetting.key == key).first()
    if not row:
        row = StoreSetting(key=key, value_json=json.dumps(value, ensure_ascii=False))
        db.add(row)
    else:
        row.value_json = json.dumps(value, ensure_ascii=False)
    log_audit(db, "settings.update", "store_setting", key, {}, auth, request)
    db.commit()
    return {"ok": True, "key": key}


@router.get("/admin/audit-logs")
def admin_audit_logs(auth: AuthContext = Depends(require_permission("audit", "read")), db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(150).all()
    return {
        "logs": [
            {
                "id": l.id, "actor_email": l.actor_email, "action": l.action,
                "resource_type": l.resource_type, "resource_id": l.resource_id,
                "details": _jload(l.details_json, {}), "ip_address": l.ip_address,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in logs
        ]
    }


@router.get("/admin/media")
def admin_list_media(folder: str = "", auth: AuthContext = Depends(require_permission("files", "read")), db: Session = Depends(get_db)):
    q = db.query(MediaFile).order_by(MediaFile.id.desc())
    if folder:
        q = q.filter(MediaFile.folder == folder)
    rows = q.limit(200).all()
    return {
        "files": [
            {
                "id": f.id, "folder": f.folder, "category": f.category, "original_name": f.original_name,
                "stored_path": f.stored_path, "mime_type": f.mime_type, "size_bytes": f.size_bytes,
                "is_private": f.is_private, "owner_id": f.owner_id, "order_id": f.order_id,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in rows
        ]
    }


@router.post("/admin/media/upload")
async def upload_media_file(
    file: UploadFile = File(...),
    folder: str = Query("store"),
    is_private: bool = Query(False),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
):
    allowed = {".png", ".jpg", ".jpeg", ".svg", ".pdf"}
    orig = Path(file.filename or "arquivo").name
    ext = Path(orig).suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Formato não permitido.")
    raw = await file.read()
    if not raw or len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Tamanho inválido (máx 15 MB).")
    if ext in (".png", ".jpg", ".jpeg"):
        try:
            with Image.open(io.BytesIO(raw)) as im:
                im.verify()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Imagem inválida.") from exc
    elif ext == ".svg":
        txt = raw.decode("utf-8", errors="ignore")
        if "<svg" not in txt.lower():
            raise HTTPException(status_code=400, detail="SVG inválido.")
        raw = re.sub(r"<script[\s\S]*?</script>", "", txt, flags=re.IGNORECASE).encode("utf-8")
    elif ext == ".pdf" and not raw.lstrip().startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="PDF inválido.")

    safe_folder = re.sub(r"[^a-z0-9_-]", "", folder.lower()) or "uploads"
    dest_dir = (PRIVATE_STORAGE_DIR if is_private else PUBLIC_UPLOADS_DIR) / safe_folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{_slugify(Path(orig).stem)}_{uuid4().hex[:8]}{ext}"
    dest = dest_dir / stored_name
    dest.write_bytes(raw)
    rel_path = str(dest.relative_to(BASE_DIR))

    mf = MediaFile(
        owner_id=auth.user.id,
        folder=safe_folder,
        category=ext.lstrip("."),
        original_name=orig,
        stored_path=rel_path,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(raw),
        is_private=is_private,
    )
    db.add(mf)
    db.commit()
    db.refresh(mf)
    return {
        "id": mf.id,
        "original_name": mf.original_name,
        "url": f"/api/files/{mf.id}/download" if is_private else f"/uploads/{safe_folder}/{stored_name}",
        "is_private": is_private,
    }


@router.get("/admin/support")
def admin_list_support(auth: AuthContext = Depends(require_permission("support", "read")), db: Session = Depends(get_db)):
    rows = db.query(SupportTicket).order_by(SupportTicket.id.desc()).all()
    users_map = {u.id: u.email for u in db.query(User).all()}
    return {
        "tickets": [
            {
                "id": t.id, "user_email": users_map.get(t.user_id, ""), "order_id": t.order_id,
                "subject": t.subject, "message": t.message, "status": t.status,
                "admin_reply": t.admin_reply, "created_at": t.created_at.isoformat(),
            }
            for t in rows
        ]
    }


@router.put("/admin/support/{ticket_id}")
def admin_reply_support(ticket_id: int, payload: SupportTicketReply, auth: AuthContext = Depends(require_permission("support", "edit")), db: Session = Depends(get_db)):
    t = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Chamado não encontrado.")
    t.status = payload.status
    t.admin_reply = payload.admin_reply
    db.commit()
    return {"ok": True}


@router.get("/admin/reports")
def admin_reports(
    export_format: str = Query("json", pattern="^(json|csv|xlsx)$"),
    auth: AuthContext = Depends(require_permission("reports", "read")),
    db: Session = Depends(get_db),
):
    orders = db.query(Order).order_by(Order.id.desc()).all()
    coupons_used = [o.coupon_code for o in orders if o.coupon_code]
    custom_items = db.query(OrderItem).filter(OrderItem.is_customized == True).count()
    approvals_total = db.query(ArtworkApproval).count()
    approvals_ok = db.query(ArtworkApproval).filter(ArtworkApproval.decision == "approved").count()

    rows_data = []
    users_map = {u.id: u for u in db.query(User).all()}
    for o in orders:
        u = users_map.get(o.user_id)
        rows_data.append(
            {
                "pedido": o.order_number,
                "cliente": u.name if u else "",
                "email": u.email if u else "",
                "status": ORDER_STATUS_LABELS.get(o.status, o.status),
                "pagamento": o.payment_status,
                "metodo": o.payment_method,
                "subtotal": o.subtotal,
                "desconto": o.discount_total,
                "frete": o.shipping_total,
                "total": o.total_amount,
                "cupom": o.coupon_code,
                "data": o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
            }
        )

    if export_format == "csv":
        buf = io.StringIO()
        headers = list(rows_data[0].keys()) if rows_data else ["pedido", "cliente", "total"]
        writer = csv.DictWriter(buf, fieldnames=headers, delimiter=";")
        writer.writeheader()
        writer.writerows(rows_data)
        return Response(
            content=buf.getvalue().encode("utf-8-sig"),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="relatorio_vendas.csv"'},
        )

    if export_format == "xlsx":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Pedidos"
        headers = list(rows_data[0].keys()) if rows_data else ["pedido", "cliente", "total"]
        ws.append(headers)
        for r in rows_data:
            ws.append([r[h] for h in headers])
        xbuf = io.BytesIO()
        wb.save(xbuf)
        return Response(
            content=xbuf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="relatorio_vendas.xlsx"'},
        )

    return {
        "summary": {
            "total_orders": len(orders),
            "total_revenue": round(sum(o.total_amount for o in orders if o.payment_status == "approved"), 2),
            "total_discounts": round(sum(o.discount_total for o in orders), 2),
            "coupons_used_count": len(coupons_used),
            "customized_items_count": custom_items,
            "artwork_approval_rate": round((approvals_ok / approvals_total * 100.0), 1) if approvals_total else 100.0,
        },
        "orders": rows_data,
    }
