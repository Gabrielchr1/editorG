"""Motor de precificação comercial no backend (nunca confia em valores do frontend)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.calendar_engine import generate_agenda_pages
from backend.models import Coupon, Order, Product, ProductVariation


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def calculate_item_price(
    product: Product,
    variation: ProductVariation | None = None,
    config: dict[str, Any] | None = None,
    selected_options: dict[str, Any] | None = None,
    quantity: int = 1,
    is_customized: bool = False,
) -> dict[str, Any]:
    """Calcula preço unitário e total de um item com detalhamento e snapshot auditável."""
    qty = max(1, int(quantity or 1))
    opts = selected_options or {}
    rules = _loads(product.pricing_rules_json, {})
    specs = _loads(product.specs_json, {})

    base_unit = float(product.promo_price) if (product.promo_price is not None and product.promo_price > 0 and product.promo_price < product.base_price) else float(product.base_price)
    var_delta = float(variation.price_delta) if variation else 0.0

    # 1. Papel / Gramatura
    paper_opts = rules.get("paper_options") or []
    paper_choice = str(opts.get("paper_option") or "")
    paper_delta = 0.0
    for po in paper_opts:
        if po.get("name") == paper_choice:
            paper_delta = float(po.get("price_delta", 0.0))
            break

    # 2. Acabamento / Encadernação
    finish_opts = rules.get("finish_options") or []
    finish_choice = str(opts.get("finish_option") or "")
    finish_delta = 0.0
    for fo in finish_opts:
        if fo.get("name") == finish_choice:
            finish_delta = float(fo.get("price_delta", 0.0))
            break

    # 3. Formato customizado no editor
    format_delta = 0.0
    if config:
        ps = config.get("page_setup", {})
        w_mm = float(ps.get("width_mm", 150.0))
        h_mm = float(ps.get("height_mm", 210.0))
        area = w_mm * h_mm
        if area > 45000:  # >= A4 aprox
            format_delta = float(rules.get("large_format_surcharge", 18.0))
        elif area > 34000:  # > A5 (ex: 17x24)
            format_delta = float(rules.get("medium_format_surcharge", 8.0))

    # 4. Páginas extras calculadas pelo motor de calendário real
    included_pages = int(rules.get("included_pages") or specs.get("page_count") or 340)
    extra_page_price = float(rules.get("extra_page_price", 0.08))
    actual_pages = included_pages
    if config:
        try:
            gen = generate_agenda_pages(config)
            actual_pages = int(gen.get("total_pages", included_pages))
        except Exception:
            actual_pages = included_pages
    elif variation and variation.page_count_override:
        actual_pages = int(variation.page_count_override)

    extra_pages = max(0, actual_pages - included_pages)
    extra_pages_delta = round(extra_pages * extra_page_price, 2)

    # 5. Taxa de personalização
    customization_fee = float(rules.get("customization_fee", 10.0)) if is_customized else 0.0

    gross_unit = round(
        base_unit + var_delta + paper_delta + finish_delta + format_delta + extra_pages_delta + customization_fee,
        2,
    )

    # 6. Desconto por volume (atacado gráfica)
    volume_tiers = sorted(
        rules.get("volume_discounts") or [
            {"min_qty": 10, "discount_pct": 8},
            {"min_qty": 30, "discount_pct": 14},
            {"min_qty": 100, "discount_pct": 20},
        ],
        key=lambda t: int(t.get("min_qty", 0)),
        reverse=True,
    )
    volume_discount_pct = 0.0
    for tier in volume_tiers:
        if qty >= int(tier.get("min_qty", 999999)):
            volume_discount_pct = float(tier.get("discount_pct", 0.0))
            break

    net_unit = round(gross_unit * (1.0 - volume_discount_pct / 100.0), 2)
    total_price = round(net_unit * qty, 2)

    return {
        "quantity": qty,
        "base_unit_price": round(base_unit, 2),
        "variation_delta": round(var_delta, 2),
        "paper_delta": round(paper_delta, 2),
        "finish_delta": round(finish_delta, 2),
        "format_delta": round(format_delta, 2),
        "included_pages": included_pages,
        "actual_pages": actual_pages,
        "extra_pages": extra_pages,
        "extra_pages_delta": extra_pages_delta,
        "customization_fee": round(customization_fee, 2),
        "gross_unit_price": gross_unit,
        "volume_discount_pct": volume_discount_pct,
        "unit_price": net_unit,
        "total_price": total_price,
        "selected_options": {
            "paper_option": paper_choice,
            "finish_option": finish_choice,
        },
    }


def calculate_shipping(subtotal: float, zip_code: str = "", shipping_cfg: dict[str, Any] | None = None) -> float:
    cfg = shipping_cfg or {}
    free_above = float(cfg.get("free_shipping_above", 250.0))
    if subtotal <= 0 or subtotal >= free_above:
        return 0.0
    clean_zip = "".join(ch for ch in (zip_code or "") if ch.isdigit())
    if not clean_zip:
        return float(cfg.get("default_shipping", 19.90))
    # Cálculo regional determinístico baseado no prefixo do CEP
    first_digit = int(clean_zip[0])
    regional_table = {
        0: 14.90, 1: 16.90, 2: 18.90, 3: 18.90,
        4: 22.90, 5: 24.90, 6: 27.90, 7: 21.90, 8: 17.90, 9: 21.90,
    }
    return regional_table.get(first_digit, 19.90)


def validate_and_apply_coupon(
    db: Session,
    coupon_code: str,
    user_id: int | None,
    items_breakdown: list[dict[str, Any]],
    subtotal: float,
    shipping_total: float,
) -> dict[str, Any]:
    """Valida regras comerciais do cupom e calcula desconto aplicável."""
    code = (coupon_code or "").strip().upper()
    if not code:
        return {"valid": False, "code": "", "discount_total": 0.0, "shipping_total": shipping_total, "reason": ""}

    coupon = db.query(Coupon).filter(Coupon.code == code).first()
    if not coupon or not coupon.is_active:
        return {"valid": False, "code": code, "discount_total": 0.0, "shipping_total": shipping_total, "reason": "Cupom inexistente ou inativo."}

    now = datetime.now(timezone.utc)
    if coupon.valid_from:
        vf = coupon.valid_from if coupon.valid_from.tzinfo else coupon.valid_from.replace(tzinfo=timezone.utc)
        if now < vf:
            return {"valid": False, "code": code, "discount_total": 0.0, "shipping_total": shipping_total, "reason": "Cupom ainda não está vigente."}
    if coupon.valid_until:
        vu = coupon.valid_until if coupon.valid_until.tzinfo else coupon.valid_until.replace(tzinfo=timezone.utc)
        if now > vu:
            return {"valid": False, "code": code, "discount_total": 0.0, "shipping_total": shipping_total, "reason": "Cupom expirado."}

    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        return {"valid": False, "code": code, "discount_total": 0.0, "shipping_total": shipping_total, "reason": "Limite global de uso do cupom atingido."}

    if user_id and coupon.max_uses_per_user is not None:
        user_uses = db.query(Order).filter(Order.user_id == user_id, Order.coupon_code == code, Order.status != "cancelado").count()
        if user_uses >= coupon.max_uses_per_user:
            return {"valid": False, "code": code, "discount_total": 0.0, "shipping_total": shipping_total, "reason": "Limite de uso por cliente atingido."}

    total_qty = sum(int(it["quantity"]) for it in items_breakdown)
    if subtotal < float(coupon.min_order_value or 0):
        return {"valid": False, "code": code, "discount_total": 0.0, "shipping_total": shipping_total, "reason": f"Valor mínimo para este cupom: R$ {coupon.min_order_value:.2f}."}
    if total_qty < int(coupon.min_quantity or 1):
        return {"valid": False, "code": code, "discount_total": 0.0, "shipping_total": shipping_total, "reason": f"Quantidade mínima de itens: {coupon.min_quantity}."}

    elig_prods = set(_loads(coupon.eligible_product_ids_json, []))
    elig_cats = set(_loads(coupon.eligible_category_ids_json, []))
    eligible_subtotal = 0.0
    for it in items_breakdown:
        p_ok = (not elig_prods) or (it["product_id"] in elig_prods)
        c_ok = (not elig_cats) or (it["category_id"] in elig_cats)
        if p_ok and c_ok:
            eligible_subtotal += float(it["total_price"])

    if eligible_subtotal <= 0:
        return {"valid": False, "code": code, "discount_total": 0.0, "shipping_total": shipping_total, "reason": "Cupom não aplicável aos produtos selecionados."}

    discount_total = 0.0
    new_shipping = shipping_total
    dtype = coupon.discount_type
    dval = float(coupon.discount_value or 0.0)

    if dtype == "percent":
        discount_total = round(eligible_subtotal * (dval / 100.0), 2)
    elif dtype == "fixed":
        discount_total = round(min(eligible_subtotal, dval), 2)
    elif dtype == "free_shipping":
        new_shipping = 0.0
        discount_total = round(shipping_total, 2)
    elif dtype == "quantity_discount":
        discount_total = round(eligible_subtotal * (dval / 100.0), 2)

    return {
        "valid": True,
        "code": code,
        "description": coupon.description,
        "discount_type": dtype,
        "discount_total": discount_total,
        "shipping_total": round(new_shipping, 2),
        "reason": "Cupom aplicado com sucesso.",
    }
