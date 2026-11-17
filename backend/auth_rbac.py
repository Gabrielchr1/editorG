"""Autenticação, RBAC granular, controle de ferramentas do editor, rate-limit, auditoria e LGPD."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.database import BASE_DIR, get_db
from backend.models import AuditLog, Notification, Role, User

SECRET_FILE = BASE_DIR / ".eg_secret"
TOKEN_TTL_HOURS = 72

bearer_scheme = HTTPBearer(auto_error=False)

# ==================== DEFINIÇÕES DE MÓDULOS E PERMISSÕES ====================

RBAC_MODULES: dict[str, dict[str, Any]] = {
    "products": {"label": "Produtos & Variações", "actions": ["read", "create", "edit", "delete", "publish"]},
    "categories": {"label": "Categorias", "actions": ["read", "create", "edit", "delete"]},
    "templates": {"label": "Biblioteca de Modelos", "actions": ["read", "create", "edit", "delete", "publish"]},
    "projects": {"label": "Projetos & Editor", "actions": ["read", "create", "edit", "delete", "export"]},
    "orders": {"label": "Pedidos", "actions": ["read", "create", "edit", "delete"]},
    "production": {"label": "Produção Gráfica & Preflight", "actions": ["read", "edit", "export", "files"]},
    "artworks": {"label": "Aprovação de Artes", "actions": ["read", "approve", "edit"]},
    "payments": {"label": "Pagamentos & Transações", "actions": ["read", "edit"]},
    "coupons": {"label": "Cupons & Promoções", "actions": ["read", "create", "edit", "delete"]},
    "users": {"label": "Usuários & Clientes", "actions": ["read", "create", "edit", "delete"]},
    "permissions": {"label": "Perfis & Permissões RBAC", "actions": ["read", "create", "edit", "delete"]},
    "libraries": {"label": "Bibliotecas Gráficas", "actions": ["read", "create", "edit", "delete"]},
    "files": {"label": "Biblioteca de Mídia & Arquivos", "actions": ["read", "create", "delete", "files"]},
    "reports": {"label": "Relatórios & Indicadores", "actions": ["read", "export"]},
    "settings": {"label": "Configurações Comerciais & Home", "actions": ["read", "edit"]},
    "audit": {"label": "Auditoria & Logs", "actions": ["read"]},
    "support": {"label": "Suporte & Chamados", "actions": ["read", "create", "edit"]},
}

EDITOR_TOOL_LABELS: dict[str, str] = {
    "edit_text": "Alterar textos e frases",
    "edit_colors": "Alterar cores CMYK",
    "edit_fonts": "Alterar famílias de fontes",
    "edit_font_size": "Alterar tamanhos de fontes",
    "add_images": "Adicionar imagens e logotipos",
    "remove_elements": "Remover elementos",
    "move_elements": "Mover elementos",
    "resize_elements": "Redimensionar elementos",
    "rotate_elements": "Rotacionar elementos",
    "create_pages": "Criar/ativar páginas especiais",
    "duplicate_pages": "Duplicar páginas/elementos",
    "delete_pages": "Excluir páginas",
    "modify_margins": "Modificar margens e segurança",
    "modify_bleed": "Modificar sangria",
    "modify_binding": "Modificar margem de encadernação",
    "modify_dimensions": "Alterar dimensões e orientação",
    "modify_calendar": "Modificar calendário e disposição",
    "modify_holidays": "Alterar feriados e datas comemorativas",
    "add_decorative": "Adicionar elementos decorativos e pautas",
    "export_preview": "Exportar/visualizar prévias",
    "download_final": "Baixar arquivos finais de impressão",
}

EDITOR_PROFILE_BASIC: dict[str, bool] = {
    k: (k in {"edit_text", "edit_colors", "export_preview"})
    for k in EDITOR_TOOL_LABELS
}

EDITOR_PROFILE_PREMIUM: dict[str, bool] = {
    k: (
        k
        in {
            "edit_text",
            "edit_colors",
            "edit_fonts",
            "edit_font_size",
            "add_images",
            "remove_elements",
            "move_elements",
            "resize_elements",
            "rotate_elements",
            "duplicate_pages",
            "add_decorative",
            "modify_holidays",
            "export_preview",
        }
    )
    for k in EDITOR_TOOL_LABELS
}

EDITOR_PROFILE_PRO: dict[str, bool] = {
    k: (k != "download_final")
    for k in EDITOR_TOOL_LABELS
}

EDITOR_PROFILE_FULL: dict[str, bool] = {k: True for k in EDITOR_TOOL_LABELS}


def normalize_editor_tools(tools: dict[str, Any] | None) -> dict[str, bool]:
    base = dict(EDITOR_PROFILE_BASIC)
    if isinstance(tools, dict):
        for k in EDITOR_TOOL_LABELS:
            if k in tools:
                base[k] = bool(tools[k])
    return base


# ==================== SEGURANÇA DE SENHAS & TOKENS ====================


def _get_secret_key() -> bytes:
    env_key = os.getenv("EG_SECRET_KEY", "").strip()
    if env_key:
        return env_key.encode("utf-8")
    if SECRET_FILE.exists():
        val = SECRET_FILE.read_text(encoding="utf-8").strip()
        if val:
            return val.encode("utf-8")
    generated = secrets.token_hex(32)
    try:
        SECRET_FILE.write_text(generated, encoding="utf-8")
    except Exception:
        pass
    return generated.encode("utf-8")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def create_access_token(user_id: int, role_slug: str, expires_hours: int = TOKEN_TTL_HOURS) -> str:
    now = int(time.time())
    header = _b64u_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
    payload = _b64u_encode(
        json.dumps(
            {
                "sub": str(user_id),
                "role": role_slug,
                "iat": now,
                "exp": now + expires_hours * 3600,
            }
        ).encode("utf-8")
    )
    msg = f"{header}.{payload}".encode("ascii")
    sig = _b64u_encode(hmac.new(_get_secret_key(), msg, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            raise ValueError("Token malformado")
        header_b, payload_b, sig_b = parts
        msg = f"{header_b}.{payload_b}".encode("ascii")
        expected_sig = _b64u_encode(hmac.new(_get_secret_key(), msg, hashlib.sha256).digest())
        if not hmac.compare_digest(sig_b, expected_sig):
            raise ValueError("Assinatura inválida")
        payload = json.loads(_b64u_decode(payload_b).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("Sessão expirada")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Token inválido ou expirado: {exc}") from exc


def get_webhook_secret() -> str:
    return os.getenv("EG_WEBHOOK_SECRET", "eg-webhook-dev-secret-2026")


def verify_webhook_signature(raw_body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False
    clean = signature_header.strip()
    if clean.startswith("sha256="):
        clean = clean[7:]
    expected = hmac.new(get_webhook_secret().encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(clean.lower(), expected.lower())


# ==================== RATE LIMITING ====================

_RATE_BUCKETS: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(bucket: str, key: str, max_calls: int = 20, window_sec: int = 60) -> None:
    if os.getenv("EG_DISABLE_RATE_LIMIT") == "1":
        return
    now = time.time()
    k = f"{bucket}:{key}"
    hits = [ts for ts in _RATE_BUCKETS[k] if now - ts < window_sec]
    if len(hits) >= max_calls:
        raise HTTPException(status_code=429, detail="Muitas tentativas recentes. Aguarde alguns segundos.")
    hits.append(now)
    _RATE_BUCKETS[k] = hits


# ==================== RESOLUÇÃO DE PERMISSÕES RBAC ====================


def resolve_user_permissions(user: User, role: Role | None) -> dict[str, list[str]]:
    """Combina permissões do perfil com overrides individuais (deny > grant)."""
    resolved: dict[str, set[str]] = {}
    if role and role.slug == "admin":
        for mod, meta in RBAC_MODULES.items():
            resolved[mod] = set(meta["actions"])
    elif role:
        try:
            role_perms = json.loads(role.permissions_json or "{}")
        except Exception:
            role_perms = {}
        for mod, acts in role_perms.items():
            if isinstance(acts, list):
                resolved[mod] = set(str(a) for a in acts)

    try:
        custom = json.loads(user.custom_permissions_json or "{}")
    except Exception:
        custom = {}

    for mod, acts in (custom.get("grant") or {}).items():
        if isinstance(acts, list):
            resolved.setdefault(mod, set()).update(str(a) for a in acts)

    for mod, acts in (custom.get("deny") or {}).items():
        if isinstance(acts, list) and mod in resolved:
            resolved[mod] -= set(str(a) for a in acts)

    return {mod: sorted(list(acts)) for mod, acts in resolved.items() if acts}


def has_permission(user: User, role: Role | None, module: str, action: str) -> bool:
    if not user.is_active:
        return False
    perms = resolve_user_permissions(user, role)
    return action in perms.get(module, [])


def is_staff_role(role: Role | None) -> bool:
    return bool(role and role.slug != "customer")


class AuthContext:
    def __init__(self, user: User, role: Role | None) -> None:
        self.user = user
        self.role = role
        self.permissions = resolve_user_permissions(user, role)

    def can(self, module: str, action: str) -> bool:
        return action in self.permissions.get(module, [])

    @property
    def is_admin(self) -> bool:
        return bool(self.role and self.role.slug == "admin")

    @property
    def is_staff(self) -> bool:
        return is_staff_role(self.role)


def get_optional_auth(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token: str | None = Query(None),
    db: Session = Depends(get_db),
) -> AuthContext | None:
    raw_token = creds.credentials if creds else token
    if not raw_token:
        return None
    payload = decode_access_token(raw_token)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active or user.is_anonymized:
        raise HTTPException(status_code=401, detail="Conta inativa ou não encontrada.")
    role = db.query(Role).filter(Role.id == user.role_id).first()
    return AuthContext(user=user, role=role)


def get_current_auth(auth: AuthContext | None = Depends(get_optional_auth)) -> AuthContext:
    if not auth:
        raise HTTPException(status_code=401, detail="Autenticação obrigatória.")
    return auth


def require_permission(module: str, action: str, staff_only: bool = True):
    def _dep(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if staff_only and not auth.is_staff:
            raise HTTPException(
                status_code=403,
                detail="Acesso negado: área restrita à equipe administrativa/produção.",
            )
        if not auth.can(module, action):
            raise HTTPException(
                status_code=403,
                detail=f"Acesso negado: permissão '{module}:{action}' necessária.",
            )
        return auth

    return _dep


def ensure_owner_or_staff(auth: AuthContext, owner_id: int | None, staff_module: str, staff_action: str = "read") -> None:
    """Garante isolamento estrito entre clientes: cliente só acessa o que é seu."""
    if owner_id is not None and owner_id == auth.user.id:
        return
    if auth.is_staff and auth.can(staff_module, staff_action):
        return
    raise HTTPException(status_code=403, detail="Você não tem permissão para acessar este recurso de outro usuário.")


# ==================== VALIDAÇÃO DE FERRAMENTAS DO EDITOR (BACKEND) ====================


def enforce_editor_tool_permissions(
    old_cfg: dict[str, Any],
    new_cfg: dict[str, Any],
    allowed_tools: dict[str, bool],
) -> None:
    """Valida no backend todas as alterações feitas por um cliente conforme perfil do produto."""

    def deny(tool_key: str) -> None:
        lbl = EDITOR_TOOL_LABELS.get(tool_key, tool_key)
        raise HTTPException(
            status_code=403,
            detail=f"Ferramenta não autorizada para este produto: {lbl} ({tool_key}).",
        )

    old_ps = old_cfg.get("page_setup", {})
    new_ps = new_cfg.get("page_setup", {})

    if not allowed_tools.get("modify_dimensions"):
        for k in ("width_mm", "height_mm", "orientation"):
            if old_ps.get(k) != new_ps.get(k):
                deny("modify_dimensions")

    if not allowed_tools.get("modify_margins"):
        for k in ("margin_top_mm", "margin_bottom_mm", "margin_outer_mm", "safety_margin_mm"):
            if old_ps.get(k) != new_ps.get(k):
                deny("modify_margins")

    if not allowed_tools.get("modify_binding"):
        for k in ("margin_inner_mm", "mirror_margins"):
            if old_ps.get(k) != new_ps.get(k):
                deny("modify_binding")

    if not allowed_tools.get("modify_bleed"):
        if old_ps.get("bleed_mm") != new_ps.get("bleed_mm"):
            deny("modify_bleed")

    old_cal = old_cfg.get("calendar", {})
    new_cal = new_cfg.get("calendar", {})

    if not allowed_tools.get("modify_calendar"):
        for k in ("year", "start_date", "end_date", "is_dated", "layout_mode", "weekend_mode", "week_starts_on", "month_display_style", "show_mini_calendar", "include_month_openers"):
            if old_cal.get(k) != new_cal.get(k):
                deny("modify_calendar")

    if not allowed_tools.get("modify_holidays"):
        for k in ("highlight_national_holidays", "state_code", "custom_holidays"):
            if old_cal.get(k) != new_cal.get(k):
                deny("modify_holidays")

    if not allowed_tools.get("edit_colors"):
        if old_cfg.get("colors") != new_cfg.get("colors"):
            deny("edit_colors")
        if old_cfg.get("ruling", {}).get("line_color") != new_cfg.get("ruling", {}).get("line_color"):
            deny("edit_colors")
        if old_cfg.get("footer", {}).get("text_color") != new_cfg.get("footer", {}).get("text_color"):
            deny("edit_colors")

    if not allowed_tools.get("add_decorative"):
        r_old = {k: v for k, v in old_cfg.get("ruling", {}).items() if k != "line_color"}
        r_new = {k: v for k, v in new_cfg.get("ruling", {}).items() if k != "line_color"}
        if r_old != r_new:
            deny("add_decorative")

    old_sp = old_cfg.get("special_pages", {})
    new_sp = new_cfg.get("special_pages", {})
    if old_sp != new_sp:
        # Alterar títulos da capa conta como edit_text; alterar páginas especiais exige create_pages/delete_pages
        for k in ("cover_title", "cover_subtitle"):
            if old_sp.get(k) != new_sp.get(k) and not allowed_tools.get("edit_text"):
                deny("edit_text")
        page_flags = ("cover_page", "personal_data", "annual_calendar", "annual_planner", "goals_page", "financial_summary", "birthdays_page", "contacts_page")
        for k in page_flags:
            if bool(old_sp.get(k)) != bool(new_sp.get(k)):
                if new_sp.get(k) and not allowed_tools.get("create_pages"):
                    deny("create_pages")
                if not new_sp.get(k) and not allowed_tools.get("delete_pages"):
                    deny("delete_pages")
        old_n = int(old_sp.get("notes_end_pages", 0))
        new_n = int(new_sp.get("notes_end_pages", 0))
        if new_n > old_n and not allowed_tools.get("create_pages"):
            deny("create_pages")
        if new_n < old_n and not allowed_tools.get("delete_pages"):
            deny("delete_pages")

    # Rodapé
    old_ft = old_cfg.get("footer", {})
    new_ft = new_cfg.get("footer", {})
    for k in ("company_name", "professional_name", "extra_text"):
        if old_ft.get(k) != new_ft.get(k) and not allowed_tools.get("edit_text"):
            deny("edit_text")
    if old_ft.get("logo_url") != new_ft.get("logo_url") and not allowed_tools.get("add_images"):
        deny("add_images")
    if (old_ft.get("font_family") != new_ft.get("font_family") or old_ft.get("bold") != new_ft.get("bold") or old_ft.get("italic") != new_ft.get("italic")) and not allowed_tools.get("edit_fonts"):
        deny("edit_fonts")
    if old_ft.get("font_size_pt") != new_ft.get("font_size_pt") and not allowed_tools.get("edit_font_size"):
        deny("edit_font_size")

    # Elementos livres
    old_els = {e["id"]: e for e in old_cfg.get("elements", []) if e.get("id")}
    new_els = {e["id"]: e for e in new_cfg.get("elements", []) if e.get("id")}

    for removed_id in set(old_els.keys()) - set(new_els.keys()):
        if not allowed_tools.get("remove_elements"):
            deny("remove_elements")

    for added_id in set(new_els.keys()) - set(old_els.keys()):
        el = new_els[added_id]
        t = el.get("type", "phrase")
        if t == "image" and not allowed_tools.get("add_images"):
            deny("add_images")
        elif t == "shape" and not allowed_tools.get("add_decorative"):
            deny("add_decorative")
        elif t == "phrase" and not allowed_tools.get("edit_text") and not allowed_tools.get("duplicate_pages"):
            deny("edit_text")

    for eid in set(old_els.keys()) & set(new_els.keys()):
        oe = old_els[eid]
        ne = new_els[eid]
        if (oe.get("text") != ne.get("text") or oe.get("alignment") != ne.get("alignment")) and not allowed_tools.get("edit_text"):
            deny("edit_text")
        if oe.get("color") != ne.get("color") and not allowed_tools.get("edit_colors"):
            deny("edit_colors")
        if (oe.get("font_family") != ne.get("font_family") or oe.get("bold") != ne.get("bold") or oe.get("italic") != ne.get("italic") or oe.get("underline") != ne.get("underline")) and not allowed_tools.get("edit_fonts"):
            deny("edit_fonts")
        if oe.get("font_size_pt") != ne.get("font_size_pt") and not allowed_tools.get("edit_font_size"):
            deny("edit_font_size")
        if (oe.get("x_mm") != ne.get("x_mm") or oe.get("y_mm") != ne.get("y_mm")) and not allowed_tools.get("move_elements"):
            deny("move_elements")
        if (oe.get("width_mm") != ne.get("width_mm") or oe.get("height_mm") != ne.get("height_mm")) and not allowed_tools.get("resize_elements"):
            deny("resize_elements")
        if oe.get("rotation_deg") != ne.get("rotation_deg") and not allowed_tools.get("rotate_elements"):
            deny("rotate_elements")
        if oe.get("image_url") != ne.get("image_url") and not allowed_tools.get("add_images"):
            deny("add_images")


# ==================== AUDITORIA & NOTIFICAÇÕES ====================


def log_audit(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: Any = "",
    details: dict[str, Any] | None = None,
    auth: AuthContext | None = None,
    request: Request | None = None,
) -> None:
    ip = ""
    if request and request.client:
        ip = request.client.host or ""
    db.add(
        AuditLog(
            actor_user_id=auth.user.id if auth else None,
            actor_email=auth.user.email if auth else "",
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            details_json=json.dumps(details or {}, ensure_ascii=False),
            ip_address=ip,
        )
    )


def create_notification_once(
    db: Session,
    user_id: int | None,
    event_key: str,
    title: str,
    message: str,
    dedup_key: str | None = None,
    channel: str = "in_app",
    metadata: dict[str, Any] | None = None,
) -> Notification | None:
    """Cria notificação idempotente (evita duplicação em reprocessamento de webhooks/eventos)."""
    if dedup_key:
        existing = db.query(Notification).filter(Notification.dedup_key == dedup_key).first()
        if existing:
            return None
    notif = Notification(
        user_id=user_id,
        event_key=event_key,
        dedup_key=dedup_key,
        channel=channel,
        title=title,
        message=message,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    )
    db.add(notif)
    return notif
