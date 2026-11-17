"""Seed comercial inicial: RBAC, usuários, categorias, modelos versionados, produtos, cupons e configs da Home."""

from __future__ import annotations

import copy
import html
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.auth_rbac import (
    EDITOR_PROFILE_BASIC,
    EDITOR_PROFILE_FULL,
    EDITOR_PROFILE_PREMIUM,
    EDITOR_PROFILE_PRO,
    RBAC_MODULES,
    hash_password,
)
from backend.models import (
    Category,
    Coupon,
    CustomerAddress,
    GraphicTemplate,
    GraphicTemplateVersion,
    Product,
    ProductVariation,
    Role,
    StoreSetting,
    User,
)
from backend.schemas import make_cmyk
from backend.seed_data import CMYK_PALETTES, build_config_from_template

BASE_DIR = Path(__file__).resolve().parent.parent
MOCKUPS_DIR = BASE_DIR / "uploads" / "demo" / "mockups"


def _cover_motif_svg(motif: str, foil: str) -> str:
    """Retorna emblema vetorial exclusivo gravado na capa frontal do produto."""
    if motif == "botanical":
        return f"""
    <g stroke="{foil}" stroke-width="2" fill="none" stroke-linecap="round" opacity="0.92">
      <path d="M332 454 C332 396 334 344 338 308"/>
      <path d="M335 426 C312 414 300 398 306 382 C322 388 332 404 335 426Z"/>
      <path d="M335 410 C358 398 370 382 364 366 C348 372 338 388 335 410Z"/>
      <path d="M336 376 C315 364 305 348 312 334 C326 340 334 356 336 376Z"/>
      <path d="M336 362 C356 350 366 334 358 320 C344 326 337 342 336 362Z"/>
      <path d="M338 328 C326 312 328 296 340 288 C349 298 347 314 338 328Z"/>
    </g>"""
    if motif == "compass":
        return f"""
    <g stroke="{foil}" fill="none" opacity="0.9">
      <circle cx="332" cy="368" r="56" stroke-width="1.4"/>
      <circle cx="332" cy="368" r="44" stroke-width="0.7" stroke-dasharray="3 4"/>
      <polygon points="332,320 342,358 380,368 342,378 332,416 322,378 284,368 322,358" stroke-width="1.3" fill="{foil}" fill-opacity="0.14"/>
      <circle cx="332" cy="368" r="6" fill="{foil}"/>
    </g>"""
    if motif == "dots_arch":
        dots = "".join(
            "".join(
                f'<circle cx="{294 + c * 15}" cy="{330 + r * 15}" r="1.7" fill="{foil}" opacity="0.78"/>'
                for c in range(6)
            )
            for r in range(5)
        )
        return f"""
    <path d="M276 420 L276 346 A56 56 0 0 1 388 346 L388 420 Z" fill="{foil}" fill-opacity="0.10" stroke="{foil}" stroke-width="1.4"/>
    {dots}"""
    if motif == "balance":
        return f"""
    <g stroke="{foil}" fill="none" stroke-width="1.6" opacity="0.92">
      <rect x="276" y="324" width="112" height="92" rx="8" fill="{foil}" fill-opacity="0.08"/>
      <line x1="292" y1="352" x2="372" y2="352" stroke-width="0.9" opacity="0.55"/>
      <rect x="296" y="376" width="14" height="28" rx="2" fill="{foil}" fill-opacity="0.35"/>
      <rect x="318" y="364" width="14" height="40" rx="2" fill="{foil}" fill-opacity="0.55"/>
      <rect x="340" y="346" width="14" height="58" rx="2" fill="{foil}" fill-opacity="0.80"/>
      <polyline points="298,366 324,352 350,336 372,340" stroke-width="1.8"/>
    </g>"""
    if motif == "crest":
        return f"""
    <g stroke="{foil}" fill="none" opacity="0.9">
      <rect x="282" y="318" width="100" height="100" rx="14" stroke-width="1.5" fill="{foil}" fill-opacity="0.08"/>
      <rect x="290" y="326" width="84" height="84" rx="10" stroke-width="0.7" opacity="0.65"/>
      <text x="332" y="379" text-anchor="middle" fill="{foil}" font-family="'Plus Jakarta Sans',sans-serif" font-size="30" font-weight="800" letter-spacing="2">B2B</text>
    </g>"""
    if motif == "arch":
        return f"""
    <g stroke="{foil}" fill="none" opacity="0.9">
      <path d="M280 416 L280 348 A52 52 0 0 1 384 348 L384 416 Z" stroke-width="1.5" fill="{foil}" fill-opacity="0.09"/>
      <line x1="296" y1="364" x2="368" y2="364" stroke-width="1"/>
      <line x1="296" y1="380" x2="368" y2="380" stroke-width="1"/>
      <line x1="296" y1="396" x2="348" y2="396" stroke-width="1"/>
    </g>"""
    if motif == "week7":
        cols = "".join(
            f'<rect x="{278 + i * 16}" y="338" width="11" height="58" rx="2.5" fill="{foil}" fill-opacity="{0.22 + (i % 3) * 0.16}" stroke="{foil}" stroke-width="0.8"/>'
            for i in range(7)
        )
        return f'<g opacity="0.95">{cols}</g>'
    if motif == "medical":
        return f"""
    <g stroke="{foil}" fill="none" opacity="0.94">
      <circle cx="332" cy="368" r="52" stroke-width="1.5" fill="{foil}" fill-opacity="0.10"/>
      <path d="M324 342 h16 v18 h18 v16 h-18 v18 h-16 v-18 h-18 v-16 h18 z" fill="{foil}" fill-opacity="0.85" stroke="none"/>
    </g>"""
    if motif == "scales":
        return f"""
    <g stroke="{foil}" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" opacity="0.92">
      <circle cx="332" cy="368" r="54" stroke-width="1.2" fill="{foil}" fill-opacity="0.08"/>
      <line x1="332" y1="328" x2="332" y2="404"/>
      <line x1="308" y1="404" x2="356" y2="404"/>
      <line x1="296" y1="344" x2="368" y2="344"/>
      <path d="M296 344 l-12 26 h24 z" fill="{foil}" fill-opacity="0.25"/>
      <path d="M368 344 l-12 26 h24 z" fill="{foil}" fill-opacity="0.25"/>
    </g>"""
    if motif == "duet":
        return f"""
    <g stroke="{foil}" fill="none" stroke-width="1.5" opacity="0.92">
      <rect x="278" y="330" width="50" height="76" rx="6" fill="{foil}" fill-opacity="0.14"/>
      <rect x="336" y="330" width="50" height="76" rx="6" fill="{foil}" fill-opacity="0.24"/>
      <text x="303" y="376" text-anchor="middle" fill="{foil}" font-family="'Plus Jakarta Sans',sans-serif" font-size="22" font-weight="800">01</text>
      <text x="361" y="376" text-anchor="middle" fill="{foil}" font-family="'Plus Jakarta Sans',sans-serif" font-size="22" font-weight="800">02</text>
    </g>"""
    return f"""
    <g stroke="{foil}" fill="none" opacity="0.92">
      <circle cx="332" cy="368" r="52" stroke-width="1.3" stroke-dasharray="4 4"/>
      <path d="M332 322 L343 357 L378 368 L343 379 L332 414 L321 379 L286 368 L321 357 Z" fill="{foil}" fill-opacity="0.22" stroke-width="1.6"/>
    </g>"""


def _ensure_editorial_mockups() -> None:
    """Gera ilustrações vetoriais SVG de capas de estúdio com design explícito."""
    MOCKUPS_DIR.mkdir(parents=True, exist_ok=True)

    specs = [
        ("mockup_agenda.svg", "#F2FBFB", "#E2F4F5", "#0ABCBF", "#078083", "#E5C17B", "Minha Agenda", "DIÁRIA EXECUTIVA • 2027", "wireo", "botanical", "EDIÇÃO A5"),
        ("mockup_permanente.svg", "#F3FAFA", "#E4F2F3", "#0E5A63", "#083B41", "#E5C17B", "Permanente", "366 PÁGINAS • USO LIVRE", "wireo", "compass", "ATEMPORAL"),
        ("mockup_planner.svg", "#F3FBF9", "#E2F5F0", "#0D8A7C", "#065A52", "#E5C17B", "Planner Atelier", "PLANEJE • REALIZE • CONQUISTE", "wireo", "dots_arch", "HÁBITOS & METAS"),
        ("mockup_financeiro.svg", "#F4FAF8", "#E5F3EE", "#115E52", "#093B33", "#E5C17B", "Financeira", "FLUXO DE CAIXA & BALANÇO", "wireo", "balance", "GESTÃO 2027"),
        ("mockup_empresarial.svg", "#F5F8F9", "#E7EEF0", "#1E2D38", "#111B22", "#0ABCBF", "Corporativa", "IDENTIDADE CMYK B2B", "hardcover", "crest", "MARCA PRÓPRIA"),
        ("mockup_moleskine.svg", "#F2FBFB", "#E0F4F5", "#099CA0", "#066B6E", "#E5C17B", "Carnet Classic", "SONHE • PLANEJE • CONQUISTE", "moleskine", "botanical", "CAPA FLEXÍVEL"),
        ("mockup_caderno.svg", "#F4F8FA", "#E6EFF3", "#164A5A", "#0C2D38", "#E5C17B", "Caderno Studio", "PAUTA SOB MEDIDA • 17×24", "wireo", "arch", "CUSTOMIZÁVEL"),
        ("mockup_semanal.svg", "#F3FAFA", "#E3F2F3", "#147A7E", "#0B5053", "#E5C17B", "Agenda Semanal", "VISÃO PANORÂMICA 7 DIAS", "wireo", "week7", "2027 • A5"),
        ("mockup_medica.svg", "#F2FBFB", "#E1F6F6", "#08A2A6", "#056C6F", "#FFFFFF", "Agenda Médica", "CLÍNICA & CONSULTÓRIO 2027", "wireo", "medical", "SAÚDE PRO"),
        ("mockup_juridica.svg", "#FAF6F7", "#F2E8EA", "#5B2333", "#3B1520", "#E5C17B", "Agenda Jurídica", "PRAZOS & AUDIÊNCIAS 2027", "hardcover", "scales", "DIREITO PRO"),
        ("mockup_2dpp.svg", "#F9F7F4", "#EFEBE4", "#5F4B36", "#3E3021", "#E5C17B", "2 Dias / Pág.", "COMPACTA EXECUTIVA 2027", "wireo", "duet", "PORTÁTIL A5"),
        ("mockup_organizador.svg", "#F4F9F9", "#E4EFF1", "#163840", "#0D2227", "#0ABCBF", "Organizador", "PROJETOS, METAS & ROTINA", "moleskine", "spark", "STUDIO FULL"),
    ]

    for fname, bg_top, bg_bot, cover_top, cover_bot, foil, title, sub, binding, motif, badge in specs:
        target = MOCKUPS_DIR / fname
        if target.exists() and "eg-studio-v5" in target.read_text(encoding="utf-8", errors="ignore"):
            continue

        title_xml = html.escape(title)
        sub_xml = html.escape(sub)
        badge_xml = html.escape(badge)

        rings = ""
        if binding == "wireo":
            rings = "".join(
                f'<rect x="132" y="{128 + i * 36}" width="34" height="7" rx="3.5" fill="url(#metalFoil)" stroke="#6B532B" stroke-width="0.5"/>'
                f'<circle cx="166" cy="{131.5 + i * 36}" r="3.2" fill="#0F1C22" opacity="0.48"/>'
                for i in range(13)
            )

        elastic = (
            f'<rect x="448" y="96" width="15" height="504" fill="{cover_bot}" opacity="0.88"/>'
            f'<rect x="448" y="96" width="2.5" height="504" fill="{foil}" opacity="0.45"/>'
            if binding == "moleskine"
            else f'<line x1="202" y1="96" x2="202" y2="600" stroke="{foil}" stroke-width="1" opacity="0.32"/>'
        )
        radius = 20 if binding == "moleskine" else 10
        motif_svg = _cover_motif_svg(motif, foil)

        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 720">
<!-- eg-studio-v5 -->
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{bg_top}"/>
      <stop offset="100%" stop-color="{bg_bot}"/>
    </linearGradient>
    <linearGradient id="coverGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{cover_top}"/>
      <stop offset="100%" stop-color="{cover_bot}"/>
    </linearGradient>
    <linearGradient id="metalFoil" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#F7E4BA"/>
      <stop offset="50%" stop-color="#D4AE6A"/>
      <stop offset="100%" stop-color="#9B773E"/>
    </linearGradient>
    <filter id="bookShadow" x="-15%" y="-15%" width="140%" height="140%">
      <feDropShadow dx="0" dy="20" stdDeviation="20" flood-color="#0F1C22" flood-opacity="0.18"/>
      <feDropShadow dx="0" dy="5" stdDeviation="6" flood-color="#0F1C22" flood-opacity="0.10"/>
    </filter>
    <filter id="softShadow" x="-15%" y="-15%" width="140%" height="140%">
      <feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#0F1C22" flood-opacity="0.10"/>
    </filter>
  </defs>
  <rect width="640" height="720" fill="url(#bg)"/>
  <circle cx="520" cy="145" r="210" fill="#FFFFFF" opacity="0.72"/>
  <rect x="44" y="44" width="552" height="632" fill="none" stroke="#FFFFFF" stroke-width="1.2" opacity="0.75"/>
  <!-- Folha Pólen decorativa ao fundo -->
  <g filter="url(#softShadow)" transform="rotate(-3 320 360)">
    <rect x="150" y="106" width="346" height="492" rx="8" fill="#FFFFFF" stroke="#D7EEEE" stroke-width="1"/>
  </g>
  <!-- Fitilho marcador em cetim -->
  <polygon points="282,598 302,598 302,654 292,642 282,654" fill="{foil}" opacity="0.92"/>
  <!-- Capa Principal 3D com Design Explícito -->
  <g filter="url(#bookShadow)">
    <!-- Bloco de miolo lateral à direita -->
    <rect x="484" y="108" width="16" height="480" rx="3" fill="#FAF8F4" stroke="#DCE7E7" stroke-width="1"/>
    <line x1="491" y1="112" x2="491" y2="584" stroke="#E6E1D6" stroke-width="0.8"/>
    <line x1="495" y1="112" x2="495" y2="584" stroke="#E6E1D6" stroke-width="0.8"/>
    <!-- Capa dura frontal -->
    <rect x="150" y="96" width="340" height="504" rx="{radius}" fill="url(#coverGrad)"/>
    <!-- Lombada com vinco editorial -->
    <rect x="150" y="96" width="32" height="504" rx="4" fill="#000000" opacity="0.16"/>
    <line x1="184" y1="98" x2="184" y2="598" stroke="#000000" stroke-width="1.4" opacity="0.22"/>
    <line x1="186" y1="98" x2="186" y2="598" stroke="#FFFFFF" stroke-width="0.7" opacity="0.18"/>
    {elastic}
    <!-- Moldura editorial em foil na capa -->
    <rect x="206" y="128" width="252" height="440" rx="8" fill="none" stroke="{foil}" stroke-width="1" opacity="0.45"/>
    <!-- Selo superior -->
    <rect x="252" y="154" width="160" height="22" rx="11" fill="{foil}" fill-opacity="0.18" stroke="{foil}" stroke-width="0.8"/>
    <text x="332" y="168.5" text-anchor="middle" fill="{foil}" font-family="'Plus Jakarta Sans',sans-serif" font-size="9.5" font-weight="700" letter-spacing="1.6">{badge_xml}</text>
    <!-- Título principal da capa -->
    <text x="332" y="232" text-anchor="middle" fill="#FFFFFF" font-family="'Plus Jakarta Sans',sans-serif" font-size="27" font-weight="800" letter-spacing="0.4">{title_xml}</text>
    <line x1="274" y1="252" x2="390" y2="252" stroke="{foil}" stroke-width="1.5"/>
    <text x="332" y="276" text-anchor="middle" fill="#FFFFFF" opacity="0.88" font-family="sans-serif" font-size="10.5" font-weight="600" letter-spacing="1.8">{sub_xml}</text>
    <!-- Ilustração temática explícita na capa -->
    {motif_svg}
    <!-- Assinatura na base da capa -->
    <text x="332" y="544" text-anchor="middle" fill="{foil}" font-family="'Plus Jakarta Sans',sans-serif" font-size="10" font-weight="700" letter-spacing="3">EDITORGRÁFICA PRO</text>
    {rings}
  </g>
</svg>"""
        target.write_text(svg, encoding="utf-8")


def _seed_roles_and_users(db: Session) -> dict[str, Role]:
    admin_perms = {m: list(meta["actions"]) for m, meta in RBAC_MODULES.items()}
    customer_perms = {
        "products": ["read"],
        "categories": ["read"],
        "templates": ["read"],
        "projects": ["read", "create", "edit", "delete", "export"],
        "orders": ["read", "create"],
        "artworks": ["read", "approve"],
        "files": ["read", "create", "files"],
        "support": ["read", "create"],
    }
    editor_1_perms = {
        "products": ["read"],
        "categories": ["read"],
        "templates": ["read", "create", "edit"],
        "projects": ["read", "edit"],
        "orders": ["read"],
        "production": ["read"],
        "artworks": ["read"],
        "libraries": ["read", "create"],
        "files": ["read", "files"],
    }
    editor_2_perms = {
        **editor_1_perms,
        "templates": ["read", "create", "edit", "publish"],
        "production": ["read", "edit", "export"],
        "artworks": ["read", "approve", "edit"],
        "libraries": ["read", "create", "edit"],
    }
    editor_3_perms = {
        **editor_2_perms,
        "products": ["read", "create", "edit"],
        "categories": ["read", "create", "edit"],
        "orders": ["read", "edit"],
        "production": ["read", "edit", "export", "files"],
        "files": ["read", "create", "delete", "files"],
        "support": ["read", "edit"],
    }
    editor_4_perms = {
        **editor_3_perms,
        "products": ["read", "create", "edit", "publish"],
        "templates": ["read", "create", "edit", "delete", "publish"],
        "coupons": ["read", "create", "edit"],
        "reports": ["read", "export"],
        "users": ["read"],
    }

    role_defs = [
        ("admin", "Administrador", "Acesso completo à plataforma comercial, produção e RBAC.", True, admin_perms),
        ("customer", "Cliente", "Acesso à loja, projetos pessoais, pedidos, aprovação de artes e downloads.", True, customer_perms),
        ("editor_1", "Editor Nível 1", "Assistente de arte e biblioteca gráfica.", True, editor_1_perms),
        ("editor_2", "Editor Nível 2", "Arte-finalista com revisão e publicação de modelos.", True, editor_2_perms),
        ("editor_3", "Editor Nível 3", "Supervisor de produção, pedidos e catálogo.", True, editor_3_perms),
        ("editor_4", "Editor Nível 4", "Gerente de estúdio e operação gráfica completa.", True, editor_4_perms),
    ]

    roles_map: dict[str, Role] = {}
    for slug, name, desc, is_sys, perms in role_defs:
        r = db.query(Role).filter(Role.slug == slug).first()
        if not r:
            r = Role(
                slug=slug,
                name=name,
                description=desc,
                is_system=is_sys,
                permissions_json=json.dumps(perms, ensure_ascii=False),
            )
            db.add(r)
            db.flush()
        roles_map[slug] = r

    users_seed = [
        ("Administrador Atelier", "admin@editorgrafica.com.br", "Admin@2026", "admin", "(11) 99999-0001"),
        ("Editor Nível 1", "editor1@editorgrafica.com.br", "Editor@2026", "editor_1", "(11) 99999-0011"),
        ("Editor Nível 2", "editor2@editorgrafica.com.br", "Editor@2026", "editor_2", "(11) 99999-0012"),
        ("Editor Nível 3", "editor3@editorgrafica.com.br", "Editor@2026", "editor_3", "(11) 99999-0013"),
        ("Editor Nível 4", "editor4@editorgrafica.com.br", "Editor@2026", "editor_4", "(11) 99999-0014"),
        ("Helena Vasconcelos (Cliente)", "cliente@editorgrafica.com.br", "Cliente@2026", "customer", "(11) 98888-7766"),
    ]
    for name, email, raw_pw, rslug, phone in users_seed:
        if not db.query(User).filter(User.email == email).first():
            u = User(
                name=name,
                email=email,
                password_hash=hash_password(raw_pw),
                phone=phone,
                role_id=roles_map[rslug].id,
                is_active=True,
                lgpd_consent=True,
            )
            db.add(u)
            db.flush()
            if rslug == "customer":
                db.add(
                    CustomerAddress(
                        user_id=u.id,
                        label="Estúdio / Comercial",
                        recipient_name=name,
                        street="Alameda Lorena",
                        number="800",
                        complement="Conjunto 42",
                        neighborhood="Jardins",
                        city="São Paulo",
                        state="SP",
                        zip_code="01424-001",
                        is_default=True,
                    )
                )
    db.commit()
    return roles_map


def _seed_categories_and_templates(db: Session) -> tuple[dict[str, Category], dict[str, GraphicTemplate]]:
    cat_defs = [
        ("Agendas Diárias", "agendas-diarias", "Um dia por página com precisão editorial para rotinas intensas.", "/uploads/demo/mockups/mockup_agenda.svg", 1),
        ("Agendas Semanais", "agendas-semanais", "Visão semanal panorâmica em layout leve e funcional.", "/uploads/demo/mockups/mockup_semanal.svg", 2),
        ("Agendas Permanentes", "agendas-permanentes", "Miolos não datados para uso livre em qualquer época do ano.", "/uploads/demo/mockups/mockup_permanente.svg", 3),
        ("Agendas Financeiras", "agendas-financeiras", "Fluxo de caixa diário, balanço mensal e metas patrimoniais.", "/uploads/demo/mockups/mockup_financeiro.svg", 4),
        ("Agendas Empresariais", "agendas-empresariais", "Edições corporativas personalizadas para marcas e equipes.", "/uploads/demo/mockups/mockup_empresarial.svg", 5),
        ("Agendas Médicas & Clínicas", "agendas-medicas", "Horários de consultas, encaixes e gestão diária de consultórios.", "/uploads/demo/mockups/mockup_medica.svg", 6),
        ("Planners", "planners", "Planners de produtividade, hábitos e planejamento estratégico.", "/uploads/demo/mockups/mockup_planner.svg", 7),
        ("Cadernetas", "cadernetas", "Cadernetas clássicas estilo Moleskine com elástico e papel pólen.", "/uploads/demo/mockups/mockup_moleskine.svg", 8),
        ("Cadernos", "cadernos", "Cadernos personalizados com pauta sob medida e encadernação nobre.", "/uploads/demo/mockups/mockup_caderno.svg", 9),
        ("Modelos Especiais", "modelos-especiais", "Organizadores pessoais e projetos gráficos totalmente sob medida.", "/uploads/demo/mockups/mockup_organizador.svg", 10),
    ]
    cats_map: dict[str, Category] = {}
    for name, slug, desc, img, order in cat_defs:
        c = db.query(Category).filter(Category.slug == slug).first()
        if not c:
            c = Category(name=name, slug=slug, description=desc, image_url=img, sort_order=order, is_active=True)
            db.add(c)
            db.flush()
        else:
            if c.image_url != img or c.sort_order != order:
                c.image_url = img
                c.sort_order = order
        cats_map[slug] = c

    admin_user = db.query(User).filter(User.email == "admin@editorgrafica.com.br").first()
    admin_id = admin_user.id if admin_user else None

    # Configs especiais para cadernetas/cadernos/segmentos baseados no motor existente
    moleskine_cfg = build_config_from_template("mensal")
    moleskine_cfg["page_setup"]["width_mm"] = 140.0
    moleskine_cfg["page_setup"]["height_mm"] = 210.0
    moleskine_cfg["ruling"]["ruling_type"] = "dotted"
    moleskine_cfg["ruling"]["line_spacing_mm"] = 5.0
    moleskine_cfg["special_pages"]["cover_title"] = "CADERNETA ATELIER"
    moleskine_cfg["special_pages"]["cover_subtitle"] = "Notas, Esboços & Projetos"

    caderno_cfg = build_config_from_template("permanente")
    caderno_cfg["page_setup"]["width_mm"] = 170.0
    caderno_cfg["page_setup"]["height_mm"] = 240.0
    caderno_cfg["ruling"]["ruling_type"] = "horizontal"
    caderno_cfg["special_pages"]["cover_title"] = "CADERNO PERSONALIZADO"
    caderno_cfg["special_pages"]["cover_subtitle"] = "Papelaria Fina CMYK"

    medica_cfg = build_config_from_template("diario")
    medica_cfg["special_pages"]["cover_title"] = "AGENDA MÉDICA & CONSULTÓRIO"
    medica_cfg["special_pages"]["cover_subtitle"] = "Agenda Clínica com Horários"

    juridica_cfg = build_config_from_template("diario")
    juridica_cfg["special_pages"]["cover_title"] = "AGENDA JURÍDICA PRO"
    juridica_cfg["special_pages"]["cover_subtitle"] = "Controle de Prazos & Audiências"

    dpp2_cfg = build_config_from_template("diario")
    dpp2_cfg["calendar"]["layout_mode"] = "2_dpp"
    dpp2_cfg["special_pages"]["cover_title"] = "AGENDA 2 DIAS POR PÁGINA"
    dpp2_cfg["special_pages"]["cover_subtitle"] = "Edição Executiva Compacta"

    tpl_defs = [
        ("Diário Clássico A5", "tpl-diario-a5", "agendas-diarias", "1_dpp", build_config_from_template("diario"), EDITOR_PROFILE_PRO),
        ("Permanente Minimalista", "tpl-permanente", "agendas-permanentes", "1_dpp", build_config_from_template("permanente"), EDITOR_PROFILE_PREMIUM),
        ("Semanal Executivo", "tpl-semanal", "agendas-semanais", "weekly", build_config_from_template("semanal"), EDITOR_PROFILE_BASIC),
        ("Agenda Médica & Clínica", "tpl-medica", "agendas-medicas", "1_dpp", medica_cfg, EDITOR_PROFILE_PRO),
        ("Agenda Jurídica & Prazos", "tpl-juridica", "agendas-diarias", "1_dpp", juridica_cfg, EDITOR_PROFILE_PRO),
        ("Agenda 2 Dias por Página", "tpl-2dpp", "agendas-diarias", "2_dpp", dpp2_cfg, EDITOR_PROFILE_PREMIUM),
        ("Planner Editorial", "tpl-planner", "planners", "planner", build_config_from_template("planner"), EDITOR_PROFILE_PRO),
        ("Planner Mensal", "tpl-mensal", "planners", "monthly", build_config_from_template("mensal"), EDITOR_PROFILE_PREMIUM),
        ("Financeiro Fluxo Diário", "tpl-financeiro", "agendas-financeiras", "financial", build_config_from_template("financeiro"), EDITOR_PROFILE_PREMIUM),
        ("Empresarial Corporativo", "tpl-empresarial", "agendas-empresariais", "corporate", build_config_from_template("empresarial"), EDITOR_PROFILE_PRO),
        ("Caderneta Estilo Moleskine", "tpl-moleskine", "cadernetas", "monthly", moleskine_cfg, EDITOR_PROFILE_PREMIUM),
        ("Caderno Studio Sob Medida", "tpl-caderno", "cadernos", "1_dpp", caderno_cfg, EDITOR_PROFILE_FULL),
    ]

    tpls_map: dict[str, GraphicTemplate] = {}
    for name, slug, cat_slug, layout, cfg, tools in tpl_defs:
        t = db.query(GraphicTemplate).filter(GraphicTemplate.slug == slug).first()
        if not t:
            t = GraphicTemplate(
                name=name,
                slug=slug,
                description=f"Modelo editorial publicado ({name})",
                category_slug=cat_slug,
                base_layout_mode=layout,
                status="published",
                current_version=1,
                allowed_tools_json=json.dumps(tools),
                is_public=True,
                created_by_id=admin_id,
            )
            db.add(t)
            db.flush()
            db.add(
                GraphicTemplateVersion(
                    template_id=t.id,
                    version_number=1,
                    config_json=json.dumps(cfg, ensure_ascii=False),
                    allowed_tools_json=json.dumps(tools),
                    changelog="Versão inicial publicada",
                    is_published=True,
                    created_by_id=admin_id,
                )
            )
        tpls_map[slug] = t

    db.commit()
    return cats_map, tpls_map


def _seed_products(db: Session, cats: dict[str, Category], tpls: dict[str, GraphicTemplate]) -> None:
    common_pricing = {
        "included_pages": 340,
        "extra_page_price": 0.10,
        "customization_fee": 14.00,
        "medium_format_surcharge": 10.00,
        "large_format_surcharge": 22.00,
        "paper_options": [
            {"name": "Offset 90g Branco", "price_delta": 0.0},
            {"name": "Pólen Soft 90g Marfim", "price_delta": 14.0},
            {"name": "Offset Premium 120g", "price_delta": 22.0},
        ],
        "finish_options": [
            {"name": "Wire-o Bronze + Capa Dura Linho", "price_delta": 0.0},
            {"name": "Costura Lombada Quadrada", "price_delta": 16.0},
            {"name": "Capa Couro Sintético + Elástico", "price_delta": 24.0},
        ],
        "volume_discounts": [
            {"min_qty": 10, "discount_pct": 8},
            {"min_qty": 30, "discount_pct": 14},
            {"min_qty": 100, "discount_pct": 22},
        ],
    }

    products_data = [
        {
            "name": "Agenda Executiva Diária 2027 — Coleção Atelier",
            "sku": "EG-AGD-2027",
            "slug": "agenda-executiva-diaria-2027",
            "cat": "agendas-diarias",
            "tpl": "tpl-diario-a5",
            "short": "Miolo 1 dia por página em CMYK com feriados automáticos e mini-calendário.",
            "full": "Projetada para rotinas executivas de alta demanda. Impressão vetorial CMYK sobre papel 90g de alta opacidade, com margem interna de encadernação calibrada e personalização completa de cores, frases e logotipo.",
            "imgs": ["/uploads/demo/mockups/mockup_agenda.svg"],
            "base": 68.90,
            "promo": 59.90,
            "cost": 21.00,
            "type": "hybrid",
            "featured": True,
            "tag": "bestseller",
            "tools": EDITOR_PROFILE_PRO,
            "specs": {
                "dimensions": "15 x 21 cm (A5)",
                "paper_type": "Pólen Soft / Offset",
                "gsm": "90 g/m²",
                "page_count": 334,
                "print_type": "Digital / Offset Alta Definição",
                "colors_info": "4x4 cores CMYK nativo",
                "binding": "Wire-o / Costura",
                "production_days": "3 a 5 dias úteis",
                "orientation": "portrait",
                "ruling_type": "horizontal",
            },
            "vars": [
                ("A5 Padrão (15x21 cm) — Datada", "-A5D", "15 x 21 cm (A5)", 150, 210, True, 0.0, None),
                ("A4 Ampla (21x29,7 cm) — Datada", "-A4D", "21 x 29,7 cm (A4)", 210, 297, True, 24.0, None),
                ("A5 Permanente (Sem Ano)", "-A5P", "15 x 21 cm (A5)", 150, 210, False, -4.0, 387),
            ],
        },
        {
            "name": "Miolo Agenda Permanente Minimalista",
            "sku": "EG-PRM-001",
            "slug": "agenda-permanente-minimalista",
            "cat": "agendas-permanentes",
            "tpl": "tpl-permanente",
            "short": "366 páginas permanentes com marcador D S T Q Q S S e abertura mensal.",
            "full": "Ideal para começar em qualquer mês sem desperdício de folhas. Personalize paletas CMYK, pautas e frases inspiradoras.",
            "imgs": ["/uploads/demo/mockups/mockup_permanente.svg"],
            "base": 54.90,
            "promo": None,
            "cost": 18.00,
            "type": "hybrid",
            "featured": True,
            "tag": "custom",
            "tools": EDITOR_PROFILE_PREMIUM,
            "specs": {
                "dimensions": "15 x 21 cm (A5)",
                "paper_type": "Offset Branco / Pólen",
                "gsm": "90 g/m²",
                "page_count": 387,
                "print_type": "CMYK Vetorial",
                "colors_info": "Paletas CMYK editáveis",
                "binding": "Wire-o / Espiral / Brochura",
                "production_days": "3 dias úteis",
                "orientation": "portrait",
                "ruling_type": "horizontal",
            },
            "vars": [
                ("A5 Permanente (15x21 cm)", "-A5", "15 x 21 cm (A5)", 150, 210, False, 0.0, 387),
                ("17x24 cm Executivo Permanente", "-1724", "17 x 24 cm", 170, 240, False, 12.0, 387),
            ],
        },
        {
            "name": "Planner Editorial Produtividade & Hábitos",
            "sku": "EG-PLN-002",
            "slug": "planner-editorial-produtividade",
            "cat": "planners",
            "tpl": "tpl-planner",
            "short": "Cronograma diário, checklist de prioridades, hábitos e pauta pontilhada.",
            "full": "Design editorial contemporâneo com equilíbrio entre agenda de horários e espaço pontilhado para reflexão e projetos.",
            "imgs": ["/uploads/demo/mockups/mockup_planner.svg"],
            "base": 79.90,
            "promo": 69.90,
            "cost": 24.00,
            "type": "hybrid",
            "featured": True,
            "tag": "new",
            "tools": EDITOR_PROFILE_PRO,
            "specs": {
                "dimensions": "15 x 21 cm (A5)",
                "paper_type": "Pólen Soft",
                "gsm": "90 g/m²",
                "page_count": 386,
                "print_type": "CMYK Editorial",
                "colors_info": "4x4 CMYK personalizado",
                "binding": "Capa Dura + Wire-o",
                "production_days": "4 dias úteis",
                "orientation": "portrait",
                "ruling_type": "dotted",
            },
            "vars": [
                ("A5 Datado Completo", "-A5D", "15 x 21 cm (A5)", 150, 210, True, 0.0, 386),
                ("A5 Permanente", "-A5P", "15 x 21 cm (A5)", 150, 210, False, 0.0, 386),
            ],
        },
        {
            "name": "Planner Financeiro Fluxo & Balanço",
            "sku": "EG-FIN-003",
            "slug": "planner-financeiro-fluxo-balanco",
            "cat": "agendas-financeiras",
            "tpl": "tpl-financeiro",
            "short": "Controle de entradas, saídas, saldo diário e planejamento financeiro anual.",
            "full": "Criado para autônomos, consultórios e empresas que controlam o fluxo diário no papel com clareza visual.",
            "imgs": ["/uploads/demo/mockups/mockup_financeiro.svg"],
            "base": 74.90,
            "promo": None,
            "cost": 22.00,
            "type": "hybrid",
            "featured": True,
            "tag": "bestseller",
            "tools": EDITOR_PROFILE_PREMIUM,
            "specs": {
                "dimensions": "15 x 21 cm (A5)",
                "paper_type": "Offset 90g / 120g",
                "gsm": "90 g/m²",
                "page_count": 387,
                "print_type": "CMYK Vetorial",
                "colors_info": "Bordô & Ouro CMYK ou personalizada",
                "binding": "Wire-o Duplo Anel",
                "production_days": "4 dias úteis",
                "orientation": "portrait",
                "ruling_type": "horizontal",
            },
            "vars": [
                ("A5 Datado", "-A5D", "15 x 21 cm (A5)", 150, 210, True, 0.0, 387),
                ("A4 Mesa Financeira", "-A4D", "21 x 29,7 cm (A4)", 210, 297, True, 22.0, 387),
            ],
        },
        {
            "name": "Agenda Empresarial Corporativa (B2B)",
            "sku": "EG-EMP-004",
            "slug": "agenda-empresarial-corporativa",
            "cat": "agendas-empresariais",
            "tpl": "tpl-empresarial",
            "short": "Com logotipo no rodapé, bloco Top 3 Prioridades e Follow-up de reuniões.",
            "full": "Solução corporativa com identidade visual da sua marca aplicada em todo o miolo e capa personalizada.",
            "imgs": ["/uploads/demo/mockups/mockup_empresarial.svg"],
            "base": 64.90,
            "promo": 54.90,
            "cost": 19.00,
            "type": "customizable",
            "featured": True,
            "tag": "custom",
            "tools": EDITOR_PROFILE_PRO,
            "specs": {
                "dimensions": "15 x 21 cm (A5)",
                "paper_type": "Offset Alta Alvura",
                "gsm": "90 g/m²",
                "page_count": 386,
                "print_type": "CMYK Institucional",
                "colors_info": "Cores institucionais CMYK",
                "binding": "Costura / Wire-o",
                "production_days": "5 dias úteis",
                "orientation": "portrait",
                "ruling_type": "horizontal",
            },
            "vars": [
                ("A5 Corporativa Datada", "-A5D", "15 x 21 cm (A5)", 150, 210, True, 0.0, 386),
                ("A5 Corporativa Permanente", "-A5P", "15 x 21 cm (A5)", 150, 210, False, -3.0, 386),
            ],
        },
        {
            "name": "Caderneta Clássica Estilo Moleskine",
            "sku": "EG-MOL-005",
            "slug": "caderneta-classica-moleskine",
            "cat": "cadernetas",
            "tpl": "tpl-moleskine",
            "short": "Cantos arredondados, capa rígida, elástico e miolo pontilhado marfim.",
            "full": "Inspirada nas cadernetas europeias clássicas de bolso e escritório. Personalize cor da pauta, monograma e frases de abertura.",
            "imgs": ["/uploads/demo/mockups/mockup_moleskine.svg"],
            "base": 49.90,
            "promo": 44.90,
            "cost": 14.50,
            "type": "hybrid",
            "featured": True,
            "tag": "new",
            "tools": EDITOR_PROFILE_PREMIUM,
            "specs": {
                "dimensions": "14 x 21 cm (Moleskine)",
                "paper_type": "Pólen Soft Marfim",
                "gsm": "90 g/m²",
                "page_count": 94,
                "print_type": "CMYK 1x1 ou 4x4",
                "colors_info": "Grafite suave / CMYK",
                "binding": "Capa Dura + Elástico + Fitilho",
                "production_days": "3 dias úteis",
                "orientation": "portrait",
                "ruling_type": "dotted",
            },
            "vars": [
                ("Moleskine Clássica (14x21 cm)", "-1421", "14 x 21 cm", 140, 210, False, 0.0, 94),
                ("Moleskine Bolso (9x14 cm)", "-0914", "9 x 14 cm", 90, 140, False, -10.0, 94),
            ],
        },
        {
            "name": "Caderno Personalizado Studio 17x24",
            "sku": "EG-CAD-006",
            "slug": "caderno-personalizado-studio",
            "cat": "cadernos",
            "tpl": "tpl-caderno",
            "short": "Formato amplo 17x24 cm com pauta configurável (linhas, quadriculada, pontilhada).",
            "full": "Liberdade total no editor para criar cadernos universitários, cadernos de consultório ou diários de projeto.",
            "imgs": ["/uploads/demo/mockups/mockup_caderno.svg"],
            "base": 58.90,
            "promo": None,
            "cost": 17.00,
            "type": "hybrid",
            "featured": False,
            "tag": "custom",
            "tools": EDITOR_PROFILE_FULL,
            "specs": {
                "dimensions": "17 x 24 cm",
                "paper_type": "Offset 90g / 120g",
                "gsm": "90 g/m²",
                "page_count": 160,
                "print_type": "CMYK Vetorial",
                "colors_info": "Totalmente editável",
                "binding": "Wire-o / Espiral Metálico",
                "production_days": "3 dias úteis",
                "orientation": "portrait",
                "ruling_type": "horizontal",
            },
            "vars": [
                ("17 x 24 cm (Universitário)", "-1724", "17 x 24 cm", 170, 240, False, 0.0, 160),
                ("A4 Grande (21 x 29,7 cm)", "-A4", "21 x 29,7 cm (A4)", 210, 297, False, 14.0, 160),
            ],
        },
        {
            "name": "Agenda Semanal Compacta Atelier",
            "sku": "EG-SEM-007",
            "slug": "agenda-semanal-compacta",
            "cat": "agendas-semanais",
            "tpl": "tpl-semanal",
            "short": "Toda a semana em uma única visão com área para metas e anotações.",
            "full": "Leve na bolsa e ágil no planejamento. Edição rápida de cores e textos no perfil básico do editor.",
            "imgs": ["/uploads/demo/mockups/mockup_semanal.svg"],
            "base": 46.90,
            "promo": 39.90,
            "cost": 14.00,
            "type": "hybrid",
            "featured": False,
            "tag": "promo",
            "tools": EDITOR_PROFILE_BASIC,
            "specs": {
                "dimensions": "15 x 21 cm (A5)",
                "paper_type": "Pólen / Offset",
                "gsm": "90 g/m²",
                "page_count": 74,
                "print_type": "CMYK Vetorial",
                "colors_info": "Terracota / Personalizada",
                "binding": "Grampeada / Costura / Wire-o",
                "production_days": "2 dias úteis",
                "orientation": "portrait",
                "ruling_type": "horizontal",
            },
            "vars": [
                ("A5 Semanal Datada", "-A5D", "15 x 21 cm (A5)", 150, 210, True, 0.0, 74),
                ("A5 Semanal Permanente", "-A5P", "15 x 21 cm (A5)", 150, 210, False, -2.0, 74),
            ],
        },
        {
            "name": "Organizador Pessoal & Projetos Sob Medida",
            "sku": "EG-ORG-008",
            "slug": "organizador-pessoal-sob-medida",
            "cat": "modelos-especiais",
            "tpl": "tpl-mensal",
            "short": "Acesso completo ao editor gráfico para criar seu organizador exclusivo.",
            "full": "Inclui calendário anual, metas, contatos, aniversários, visão mensal e semanas personalizadas com todas as ferramentas liberadas.",
            "imgs": ["/uploads/demo/mockups/mockup_organizador.svg"],
            "base": 84.90,
            "promo": None,
            "cost": 26.00,
            "type": "customizable",
            "featured": True,
            "tag": "custom",
            "tools": EDITOR_PROFILE_FULL,
            "specs": {
                "dimensions": "15 x 21 cm (A5)",
                "paper_type": "Pólen Soft 90g / Offset 120g",
                "gsm": "90 g/m²",
                "page_count": 94,
                "print_type": "CMYK Alta Fidelidade",
                "colors_info": "Cartela CMYK livre",
                "binding": "Wire-o / Capa Dura",
                "production_days": "4 dias úteis",
                "orientation": "portrait",
                "ruling_type": "dotted",
            },
            "vars": [
                ("A5 Organizador Completo", "-A5", "15 x 21 cm (A5)", 150, 210, True, 0.0, 94),
                ("A4 Mesa Editorial", "-A4", "21 x 29,7 cm (A4)", 210, 297, True, 20.0, 94),
            ],
        },
        {
            "name": "Caderneta Moleskine Marfim Edição Pronta",
            "sku": "EG-MOL-009",
            "slug": "caderneta-moleskine-marfim-pronta",
            "cat": "cadernetas",
            "tpl": "tpl-moleskine",
            "short": "Produto pronto para envio imediato: capa rígida grafite e papel marfim.",
            "full": "Acabamento artesanal com gravação discreta e papel Pólen Soft 90g amigo da caneta-tinteiro.",
            "imgs": ["/uploads/demo/mockups/mockup_moleskine.svg"],
            "base": 42.90,
            "promo": None,
            "cost": 12.00,
            "type": "ready",
            "featured": False,
            "tag": "bestseller",
            "tools": EDITOR_PROFILE_BASIC,
            "specs": {
                "dimensions": "14 x 21 cm",
                "paper_type": "Pólen Soft Marfim",
                "gsm": "90 g/m²",
                "page_count": 94,
                "print_type": "Impressão 1x1 K Puro",
                "colors_info": "Grafite Suave",
                "binding": "Capa Dura + Elástico",
                "production_days": "Pronta Entrega",
                "orientation": "portrait",
                "ruling_type": "dotted",
            },
            "vars": [
                ("Marfim Pontilhada 14x21 cm", "-DOT", "14 x 21 cm", 140, 210, False, 0.0, 94),
            ],
        },
        {
            "name": "Agenda Médica & Consultório 2027",
            "sku": "EG-MED-010",
            "slug": "agenda-medica-clinica-2027",
            "cat": "agendas-medicas",
            "tpl": "tpl-medica",
            "short": "Grade horária clínica de 30 em 30 minutos com registro de pacientes e procedimentos.",
            "full": "Desenvolvida para médicos, dentistas e clínicas. Personalize cabeçalho com logotipo do consultório, horários de atendimento e cores institucionais em CMYK.",
            "imgs": ["/uploads/demo/mockups/mockup_medica.svg"],
            "base": 72.90,
            "promo": 64.90,
            "cost": 22.00,
            "type": "hybrid",
            "featured": True,
            "tag": "new",
            "tools": EDITOR_PROFILE_PRO,
            "specs": {
                "dimensions": "15 x 21 cm (A5)",
                "paper_type": "Offset 90g / 120g",
                "gsm": "90 g/m²",
                "page_count": 334,
                "print_type": "CMYK Vetorial",
                "colors_info": "Ciano Clínico / Personalizável",
                "binding": "Capa Dura + Wire-o",
                "production_days": "3 a 5 dias úteis",
                "orientation": "portrait",
                "ruling_type": "horizontal",
            },
            "vars": [
                ("A5 Consultório Datada", "-A5D", "15 x 21 cm (A5)", 150, 210, True, 0.0, 334),
                ("17x24 cm Clínica Ampliada", "-1724", "17 x 24 cm", 170, 240, True, 16.0, 334),
            ],
        },
        {
            "name": "Agenda Jurídica Prazos & Audiências 2027",
            "sku": "EG-JUR-011",
            "slug": "agenda-juridica-prazos-2027",
            "cat": "agendas-diarias",
            "tpl": "tpl-juridica",
            "short": "Controle rigoroso de intimações, prazos processuais e pauta diária de audiências.",
            "full": "Edição clássica voltada para advogados e escritórios de advocacia. Inclui blocos dedicados para número do processo, vara, fórum e follow-up.",
            "imgs": ["/uploads/demo/mockups/mockup_juridica.svg"],
            "base": 76.90,
            "promo": None,
            "cost": 23.00,
            "type": "hybrid",
            "featured": False,
            "tag": "new",
            "tools": EDITOR_PROFILE_PRO,
            "specs": {
                "dimensions": "15 x 21 cm (A5)",
                "paper_type": "Pólen Soft 90g",
                "gsm": "90 g/m²",
                "page_count": 334,
                "print_type": "CMYK Editorial",
                "colors_info": "Bordeaux & Dourado ou CMYK livre",
                "binding": "Capa Dura Costurada",
                "production_days": "4 dias úteis",
                "orientation": "portrait",
                "ruling_type": "horizontal",
            },
            "vars": [
                ("A5 Jurídica Datada", "-A5D", "15 x 21 cm (A5)", 150, 210, True, 0.0, 334),
            ],
        },
        {
            "name": "Agenda Executiva 2 Dias por Página 2027",
            "sku": "EG-2DP-012",
            "slug": "agenda-2-dias-pagina-2027",
            "cat": "agendas-diarias",
            "tpl": "tpl-2dpp",
            "short": "Equilíbrio perfeito entre leveza na bolsa e espaço organizado para cada data.",
            "full": "Dois dias completos em cada face, mantendo feriados nacionais, calendário de referência e personalização completa de cores no estúdio.",
            "imgs": ["/uploads/demo/mockups/mockup_2dpp.svg"],
            "base": 56.90,
            "promo": 49.90,
            "cost": 16.50,
            "type": "hybrid",
            "featured": False,
            "tag": "promo",
            "tools": EDITOR_PROFILE_PREMIUM,
            "specs": {
                "dimensions": "15 x 21 cm (A5)",
                "paper_type": "Offset / Pólen 90g",
                "gsm": "90 g/m²",
                "page_count": 208,
                "print_type": "CMYK Vetorial",
                "colors_info": "Personalizável",
                "binding": "Wire-o / Espiral",
                "production_days": "3 dias úteis",
                "orientation": "portrait",
                "ruling_type": "horizontal",
            },
            "vars": [
                ("A5 2 Dias/Página Datada", "-A5D", "15 x 21 cm (A5)", 150, 210, True, 0.0, 208),
                ("A5 2 Dias/Página Permanente", "-A5P", "15 x 21 cm (A5)", 150, 210, False, -3.0, 208),
            ],
        },
    ]

    for p in products_data:
        existing_prod = db.query(Product).filter(Product.slug == p["slug"]).first()
        if existing_prod:
            if p["slug"] == "organizador-pessoal-sob-medida" and existing_prod.images_json == '["/uploads/demo/mockups/mockup_planner.svg"]':
                existing_prod.images_json = json.dumps(p["imgs"])
                existing_prod.mockups_json = json.dumps(p["imgs"])
            continue
        cat_obj = cats[p["cat"]]
        tpl_obj = tpls[p["tpl"]]
        rules = copy.deepcopy(common_pricing)
        rules["included_pages"] = p["specs"]["page_count"]
        prod = Product(
            name=p["name"],
            sku=p["sku"],
            slug=p["slug"],
            category_id=cat_obj.id,
            short_description=p["short"],
            full_description=p["full"],
            images_json=json.dumps(p["imgs"]),
            mockups_json=json.dumps(p["imgs"]),
            demo_file_url="",
            base_price=p["base"],
            promo_price=p["promo"],
            cost_price=p["cost"],
            product_type=p["type"],
            status="active",
            is_available=True,
            stock_qty=500,
            is_featured=p["featured"],
            commercial_tag=p["tag"],
            is_customizable=(p["type"] != "ready"),
            template_id=tpl_obj.id,
            allowed_tools_json=json.dumps(p["tools"]),
            pricing_rules_json=json.dumps(rules, ensure_ascii=False),
            specs_json=json.dumps(p["specs"], ensure_ascii=False),
            sales_count=25 if p["tag"] == "bestseller" else 8,
        )
        db.add(prod)
        db.flush()
        for idx, (vname, vsuf, vfmt, vw, vh, vdated, vdelta, vpages) in enumerate(p["vars"]):
            db.add(
                ProductVariation(
                    product_id=prod.id,
                    name=vname,
                    sku_suffix=vsuf,
                    format_label=vfmt,
                    width_mm=vw,
                    height_mm=vh,
                    is_dated=vdated,
                    price_delta=vdelta,
                    page_count_override=vpages,
                    is_active=True,
                    sort_order=idx,
                )
            )
    db.commit()


def _seed_coupons_and_settings(db: Session) -> None:
    coupons_seed = [
        ("BEMVINDO10", "10% de desconto na primeira compra", "percent", 10.0, 40.0, 1, 500, 1),
        ("FRETEGRATIS", "Frete grátis acima de R$ 100,00", "free_shipping", 0.0, 100.0, 1, 1000, 3),
        ("ATACADO15", "15% para pedidos a partir de 5 unidades", "quantity_discount", 15.0, 150.0, 5, 500, 5),
    ]
    for code, desc, dtype, val, min_v, min_q, max_u, max_pu in coupons_seed:
        if not db.query(Coupon).filter(Coupon.code == code).first():
            db.add(
                Coupon(
                    code=code,
                    description=desc,
                    discount_type=dtype,
                    discount_value=val,
                    min_order_value=min_v,
                    min_quantity=min_q,
                    max_uses=max_u,
                    max_uses_per_user=max_pu,
                    is_active=True,
                )
            )

    default_settings: dict[str, Any] = {
        "store_identity": {
            "store_name": "EditorGráfica Atelier",
            "tagline": "Papelaria Fina, Agendas Sob Medida & Impressão CMYK",
            "logo_url": "/uploads/demo/logo_grafica_demo.svg",
            "contact_email": "atendimento@editorgrafica.com.br",
            "contact_phone": "(11) 3040-8800",
            "whatsapp": "(11) 99999-0001",
            "address": "Rua Bela Cintra, 1200 — Jardins, São Paulo/SP",
            "currency": "BRL",
            "production_lead_time": "3 a 5 dias úteis após aprovação da arte",
        },
        "home_content": {
            "hero_eyebrow": "ALTA PAPELARIA & IMPRESSÃO GRÁFICA EM CMYK",
            "hero_title": "Agendas, planners e cadernetas desenhados com precisão editorial.",
            "hero_subtitle": "Escolha edições prontas em papel Pólen e Offset ou abra nosso estúdio gráfico online para personalizar datas, cores CMYK, pautas, frases e sua marca antes da impressão.",
            "hero_primary_cta": "Personalizar Agora",
            "hero_secondary_cta": "Explorar Catálogo",
            "hero_image": "/static/js/imgs/imgag.png",
            "benefits": [
                {"title": "Impressão 100% CMYK Vetorial", "desc": "Fidelidade cromática calibrada para gráfica profissional, com sangria de 3 mm e marcas de corte."},
                {"title": "Papéis Nobres 90g e 120g", "desc": "Pólen Soft marfim e Offset de alta alvura com encadernação em Wire-o ou costura artesanal."},
                {"title": "Aprovação de Arte Online", "desc": "Receba a prévia fiel do seu miolo para aprovar antes da produção entrar em máquina."},
                {"title": "Produção em Escala B2B", "desc": "Descontos progressivos para empresas, clínicas, escritórios e brindes corporativos."},
            ],
            "testimonials": [
                {"author": "Dra. Camila Ribeiro", "role": "Clínica Dermatológica Jardins", "quote": "Personalizamos 180 agendas com nossa paleta CMYK exata e logotipo no rodapé. O preflight garantiu zero erros."},
                {"author": "Rafael Nogueira", "role": "Nogueira & Associados Advocacia", "quote": "A qualidade das cadernetas estilo Moleskine e a facilidade de aprovar a arte online superaram qualquer gráfica tradicional."},
                {"author": "Beatriz Montefiori", "role": "Consultora Financeira", "quote": "O planner financeiro diário permitiu ajustar exatamente as colunas que uso com meus clientes."},
            ],
            "faqs": [
                {"q": "Como funciona a personalização no editor online?", "a": "Ao clicar em 'Personalizar este modelo', você acessa nosso estúdio gráfico diretamente com as ferramentas liberadas para aquele produto. Tudo é validado em tempo real."},
                {"q": "As cores impressas ficam fiéis ao que configuro?", "a": "Sim. Toda a plataforma trabalha nativamente em cartela CMYK, gerando PDF vetorial pronto para pré-impressão."},
                {"q": "Posso aprovar a arte antes de imprimir?", "a": "Sim! Após o pagamento confirmado, nossa equipe gera a prévia em PDF e você aprova ou solicita ajustes diretamente na Área do Cliente."},
                {"q": "Há descontos para empresas e grandes quantidades?", "a": "Sim, pedidos acima de 10, 30 e 100 unidades recebem descontos progressivos automáticos no carrinho."},
            ],
        },
        "payment_shipping": {
            "pix_enabled": True,
            "mercadopago_enabled": True,
            "free_shipping_above": 250.0,
            "default_shipping": 19.90,
        },
        "policies": {
            "terms": "Os produtos personalizados são produzidos sob demanda após aprovação explícita da arte pelo cliente.",
            "privacy": "Seus dados pessoais e arquivos enviados são protegidos conforme a LGPD e isolados por conta.",
            "retention_days": 365,
        },
    }

    for key, val in default_settings.items():
        if not db.query(StoreSetting).filter(StoreSetting.key == key).first():
            db.add(StoreSetting(key=key, value_json=json.dumps(val, ensure_ascii=False)))

    db.commit()


def seed_ecommerce_data(db: Session) -> None:
    """Popula todo o ecossistema comercial de forma idempotente."""
    _ensure_editorial_mockups()
    _seed_roles_and_users(db)
    cats, tpls = _seed_categories_and_templates(db)
    _seed_products(db, cats, tpls)
    _seed_coupons_and_settings(db)
