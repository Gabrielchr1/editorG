"""Modelos SQLAlchemy da plataforma EditorGráfica Pro (Editor + E-Commerce Gráfico)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ==================== MODELOS ORIGINAIS DO EDITOR ====================


class Project(Base):
    """Representa um projeto independente de miolo de agenda (Studio ou Cliente)."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    client_name = Column(String(200), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    year = Column(Integer, nullable=False, default=2026)
    template_type = Column(String(64), nullable=False, default="1_dpp")
    format_name = Column(String(64), nullable=False, default="15 x 21 cm (A5)")
    config_json = Column(Text, nullable=False)
    thumbnail_svg = Column(Text, nullable=False, default="")
    page_count = Column(Integer, nullable=False, default=0)
    is_favorite = Column(Integer, nullable=False, default=0)
    last_exported_at = Column(String(64), nullable=True)

    # Colunas adicionadas na expansão comercial (migração incremental v3)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    template_id = Column(Integer, ForeignKey("graphic_templates.id"), nullable=True)
    template_version = Column(Integer, nullable=False, default=1, server_default="1")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    status = Column(String(32), nullable=False, default="draft", server_default="draft")
    customization_options_json = Column(Text, nullable=False, default="{}", server_default="{}")

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class LibraryItem(Base):
    """Biblioteca reutilizável de logotipos, frases, paletas CMYK e elementos gráficos."""

    __tablename__ = "library_items"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False, index=True)  # logo | phrase | palette | graphic | font
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    tags = Column(Text, nullable=False, default="")
    content_json = Column(Text, nullable=False, default="{}")
    file_path = Column(String(500), nullable=False, default="")
    is_system = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


# ==================== USUÁRIOS, RBAC & ENDEREÇOS ====================


class Role(Base):
    """Perfis RBAC configuráveis (Admin, Cliente, Editores 1..4 e perfis customizados)."""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False, default="")
    is_system = Column(Boolean, nullable=False, default=False)
    permissions_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class User(Base):
    """Usuário da plataforma (Administrador, Editor ou Cliente)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(180), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(40), nullable=False, default="")
    document_cpf_cnpj = Column(String(32), nullable=False, default="")
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False, index=True)
    custom_permissions_json = Column(Text, nullable=False, default="{}")
    is_active = Column(Boolean, nullable=False, default=True)
    lgpd_consent = Column(Boolean, nullable=False, default=True)
    lgpd_consent_at = Column(DateTime(timezone=True), nullable=True)
    is_anonymized = Column(Boolean, nullable=False, default=False)
    reset_token_hash = Column(String(128), nullable=True)
    reset_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class CustomerAddress(Base):
    """Endereços de entrega cadastrados pelo cliente."""

    __tablename__ = "customer_addresses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    label = Column(String(80), nullable=False, default="Principal")
    recipient_name = Column(String(180), nullable=False)
    street = Column(String(220), nullable=False)
    number = Column(String(32), nullable=False)
    complement = Column(String(120), nullable=False, default="")
    neighborhood = Column(String(120), nullable=False, default="")
    city = Column(String(120), nullable=False)
    state = Column(String(16), nullable=False)
    zip_code = Column(String(20), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


# ==================== CATÁLOGO, MODELOS GRÁFICOS & PRODUTOS ====================


class Category(Base):
    """Categorias comerciais da loja gráfica."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(140), nullable=False)
    slug = Column(String(140), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    image_url = Column(String(500), nullable=False, default="")
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class GraphicTemplate(Base):
    """Biblioteca de modelos gráficos versionados e publicáveis."""

    __tablename__ = "graphic_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False, default="")
    category_slug = Column(String(120), nullable=False, default="agendas-diarias")
    base_layout_mode = Column(String(64), nullable=False, default="1_dpp")
    status = Column(String(32), nullable=False, default="published", index=True)  # draft | published | unpublished | archived
    current_version = Column(Integer, nullable=False, default=1)
    allowed_tools_json = Column(Text, nullable=False, default="{}")
    is_public = Column(Boolean, nullable=False, default=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class GraphicTemplateVersion(Base):
    """Versão imutável publicada de um modelo gráfico."""

    __tablename__ = "graphic_template_versions"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("graphic_templates.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    config_json = Column(Text, nullable=False)
    allowed_tools_json = Column(Text, nullable=False, default="{}")
    changelog = Column(Text, nullable=False, default="")
    is_published = Column(Boolean, nullable=False, default=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("template_id", "version_number", name="uq_tpl_version"),)


class Product(Base):
    """Produto comercializável na loja (pronto, personalizável ou híbrido)."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(220), nullable=False, index=True)
    sku = Column(String(80), unique=True, nullable=False, index=True)
    slug = Column(String(220), unique=True, nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, index=True)
    short_description = Column(Text, nullable=False, default="")
    full_description = Column(Text, nullable=False, default="")
    images_json = Column(Text, nullable=False, default="[]")
    mockups_json = Column(Text, nullable=False, default="[]")
    demo_file_url = Column(String(500), nullable=False, default="")
    base_price = Column(Float, nullable=False, default=49.90)
    promo_price = Column(Float, nullable=True)
    cost_price = Column(Float, nullable=False, default=0.0)
    product_type = Column(String(32), nullable=False, default="hybrid")  # ready | customizable | hybrid
    status = Column(String(32), nullable=False, default="active", index=True)  # active | draft | archived
    is_available = Column(Boolean, nullable=False, default=True)
    stock_qty = Column(Integer, nullable=False, default=999)
    is_featured = Column(Boolean, nullable=False, default=False)
    commercial_tag = Column(String(40), nullable=False, default="")  # bestseller | new | promo | custom | ""
    is_customizable = Column(Boolean, nullable=False, default=True)
    template_id = Column(Integer, ForeignKey("graphic_templates.id"), nullable=True)
    allowed_tools_json = Column(Text, nullable=False, default="{}")
    pricing_rules_json = Column(Text, nullable=False, default="{}")
    specs_json = Column(Text, nullable=False, default="{}")
    sales_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ProductVariation(Base):
    """Variações de formato, datação e preço de um produto."""

    __tablename__ = "product_variations"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    name = Column(String(140), nullable=False)
    sku_suffix = Column(String(40), nullable=False, default="")
    format_label = Column(String(80), nullable=False, default="15 x 21 cm (A5)")
    width_mm = Column(Float, nullable=False, default=150.0)
    height_mm = Column(Float, nullable=False, default=210.0)
    is_dated = Column(Boolean, nullable=False, default=True)
    price_delta = Column(Float, nullable=False, default=0.0)
    page_count_override = Column(Integer, nullable=True)
    extra_specs_json = Column(Text, nullable=False, default="{}")
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)


class ProjectVersion(Base):
    """Histórico de versões salvas de um projeto de cliente."""

    __tablename__ = "project_versions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    config_json = Column(Text, nullable=False)
    customization_options_json = Column(Text, nullable=False, default="{}")
    saved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(String(255), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Favorite(Base):
    """Produtos favoritados pelo cliente."""

    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_user_fav"),)


# ==================== CARRINHO, CUPONS, PEDIDOS & PAGAMENTOS ====================


class Cart(Base):
    """Carrinho de compras persistente."""

    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_token = Column(String(120), nullable=True, index=True)
    coupon_code = Column(String(64), nullable=False, default="")
    zip_code = Column(String(20), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class CartItem(Base):
    """Item do carrinho (produto pronto ou com projeto personalizado vinculado)."""

    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey("carts.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variation_id = Column(Integer, ForeignKey("product_variations.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    project_version = Column(Integer, nullable=True)
    is_customized = Column(Boolean, nullable=False, default=False)
    selected_options_json = Column(Text, nullable=False, default="{}")
    quantity = Column(Integer, nullable=False, default=1)
    unit_price_cached = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Coupon(Base):
    """Cupons e campanhas promocionais."""

    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=False, default="")
    discount_type = Column(String(32), nullable=False, default="percent")  # percent | fixed | free_shipping | quantity_discount
    discount_value = Column(Float, nullable=False, default=10.0)
    min_order_value = Column(Float, nullable=False, default=0.0)
    min_quantity = Column(Integer, nullable=False, default=1)
    max_uses = Column(Integer, nullable=True)
    max_uses_per_user = Column(Integer, nullable=True)
    used_count = Column(Integer, nullable=False, default=0)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)
    eligible_product_ids_json = Column(Text, nullable=False, default="[]")
    eligible_category_ids_json = Column(Text, nullable=False, default="[]")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Order(Base):
    """Pedido comercial com rastreamento de pagamento e produção."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(40), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(48), nullable=False, default="aguardando_pagamento", index=True)
    subtotal = Column(Float, nullable=False, default=0.0)
    discount_total = Column(Float, nullable=False, default=0.0)
    shipping_total = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    coupon_code = Column(String(64), nullable=False, default="")
    shipping_address_json = Column(Text, nullable=False, default="{}")
    payment_method = Column(String(40), nullable=False, default="pix")
    payment_status = Column(String(32), nullable=False, default="pending", index=True)
    assigned_editor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    priority = Column(String(24), nullable=False, default="normal")
    customer_notes = Column(Text, nullable=False, default="")
    internal_notes = Column(Text, nullable=False, default="")
    pricing_rules_snapshot_json = Column(Text, nullable=False, default="{}")
    paid_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class OrderItem(Base):
    """Item de pedido com snapshot imutável de preço, configuração e arquivos."""

    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variation_id = Column(Integer, nullable=True)
    project_id = Column(Integer, nullable=True)
    project_version = Column(Integer, nullable=True)
    product_name = Column(String(220), nullable=False)
    variation_name = Column(String(160), nullable=False, default="")
    sku = Column(String(80), nullable=False, default="")
    is_customized = Column(Boolean, nullable=False, default=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0.0)
    total_price = Column(Float, nullable=False, default=0.0)
    cost_unit_snapshot = Column(Float, nullable=False, default=0.0)
    selected_options_json = Column(Text, nullable=False, default="{}")
    pricing_snapshot_json = Column(Text, nullable=False, default="{}")
    immutable_config_snapshot_json = Column(Text, nullable=False, default="{}")
    preview_file_id = Column(Integer, ForeignKey("media_files.id"), nullable=True)
    final_file_id = Column(Integer, ForeignKey("media_files.id"), nullable=True)
    preflight_report_json = Column(Text, nullable=False, default="{}")
    artwork_status = Column(String(32), nullable=False, default="pending")  # pending | awaiting_approval | approved | changes_requested
    approved_version = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class OrderStatusHistory(Base):
    """Linha do tempo imutável de transições de status do pedido."""

    __tablename__ = "order_status_history"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    from_status = Column(String(48), nullable=False, default="")
    to_status = Column(String(48), nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class ArtworkApproval(Base):
    """Registro auditável de aprovação ou solicitação de ajuste de arte pelo cliente."""

    __tablename__ = "artwork_approvals"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False, index=True)
    project_version = Column(Integer, nullable=False, default=1)
    decision = Column(String(32), nullable=False)  # approved | changes_requested
    comments = Column(Text, nullable=False, default="")
    decided_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    preview_file_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class PaymentTransaction(Base):
    """Transações financeiras com Pix / Mercado Pago e controle de idempotência."""

    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    provider = Column(String(40), nullable=False, default="pix")
    external_id = Column(String(140), nullable=False, index=True)
    idempotency_key = Column(String(140), unique=True, nullable=False)
    status = Column(String(32), nullable=False, default="pending")
    amount = Column(Float, nullable=False, default=0.0)
    qr_code_payload = Column(Text, nullable=False, default="")
    checkout_url = Column(String(500), nullable=False, default="")
    raw_payload_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


# ==================== MÍDIA PRIVADA, NOTIFICAÇÕES, AUDITORIA, CONFIGS & SUPORTE ====================


class MediaFile(Base):
    """Biblioteca centralizada e segura de arquivos (privados de clientes e públicos da loja)."""

    __tablename__ = "media_files"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    order_id = Column(Integer, nullable=True, index=True)
    project_id = Column(Integer, nullable=True, index=True)
    folder = Column(String(64), nullable=False, default="uploads", index=True)
    category = Column(String(64), nullable=False, default="image")
    original_name = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)
    mime_type = Column(String(120), nullable=False, default="application/octet-stream")
    size_bytes = Column(Integer, nullable=False, default=0)
    is_private = Column(Boolean, nullable=False, default=False)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Notification(Base):
    """Notificações internas, e-mail e WhatsApp com proteção contra duplicidade."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    event_key = Column(String(80), nullable=False, index=True)
    dedup_key = Column(String(160), unique=True, nullable=True)
    channel = Column(String(32), nullable=False, default="in_app")
    title = Column(String(220), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base):
    """Auditoria de operações administrativas, permissões e segurança."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, nullable=True, index=True)
    actor_email = Column(String(200), nullable=False, default="")
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(80), nullable=False, default="")
    resource_id = Column(String(80), nullable=False, default="")
    details_json = Column(Text, nullable=False, default="{}")
    ip_address = Column(String(64), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class StoreSetting(Base):
    """Configurações comerciais dinâmicas, conteúdo da Home, frete e políticas."""

    __tablename__ = "store_settings"

    key = Column(String(100), primary_key=True)
    value_json = Column(Text, nullable=False, default="{}")
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class SupportTicket(Base):
    """Chamados de suporte de clientes vinculados opcionalmente a pedidos."""

    __tablename__ = "support_tickets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    order_id = Column(Integer, nullable=True)
    subject = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="open")  # open | in_progress | resolved | closed
    admin_reply = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
