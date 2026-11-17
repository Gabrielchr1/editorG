"""Modelos prontos de miolo, paletas CMYK gráficas, pacotes de frases e seed inicial."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.calendar_engine import generate_agenda_pages
from backend.models import LibraryItem, Project
from backend.schemas import default_project_config, make_cmyk

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"

CMYK_PALETTES: list[dict[str, Any]] = [
    {
        "id": "pal_executivo",
        "name": "Clássico Executivo",
        "description": "Azul marinho profundo com acento âmbar e cinza neutro (CMYK).",
        "colors": {
            "palette_name": "Clássico Executivo",
            "title_color": make_cmyk(90, 70, 20, 35),
            "weekday_color": make_cmyk(60, 45, 25, 20),
            "date_number_color": make_cmyk(95, 75, 20, 40),
            "ruling_line_color": make_cmyk(0, 0, 0, 25),
            "decorative_color": make_cmyk(45, 30, 10, 10),
            "highlight_color": make_cmyk(15, 45, 90, 5),
            "weekend_color": make_cmyk(15, 75, 70, 15),
            "holiday_color": make_cmyk(0, 90, 80, 10),
            "background_color": make_cmyk(0, 0, 0, 0),
        },
    },
    {
        "id": "pal_pb_economica",
        "name": "Monocromático 100% K (P&B)",
        "description": "Ideal para impressão 1x1 cor (apenas chapa Preta K), máxima economia.",
        "colors": {
            "palette_name": "Monocromático 100% K (P&B)",
            "title_color": make_cmyk(0, 0, 0, 95),
            "weekday_color": make_cmyk(0, 0, 0, 65),
            "date_number_color": make_cmyk(0, 0, 0, 100),
            "ruling_line_color": make_cmyk(0, 0, 0, 25),
            "decorative_color": make_cmyk(0, 0, 0, 45),
            "highlight_color": make_cmyk(0, 0, 0, 80),
            "weekend_color": make_cmyk(0, 0, 0, 75),
            "holiday_color": make_cmyk(0, 0, 0, 90),
            "background_color": make_cmyk(0, 0, 0, 0),
        },
    },
    {
        "id": "pal_clinico",
        "name": "Clínico & Saúde (Verde Sálvia)",
        "description": "Tons suaves de verde sálvia e grafite, ideal para clínicas e consultórios.",
        "colors": {
            "palette_name": "Clínico & Saúde (Verde Sálvia)",
            "title_color": make_cmyk(60, 20, 50, 35),
            "weekday_color": make_cmyk(45, 15, 40, 20),
            "date_number_color": make_cmyk(65, 22, 55, 40),
            "ruling_line_color": make_cmyk(10, 0, 10, 20),
            "decorative_color": make_cmyk(35, 10, 30, 10),
            "highlight_color": make_cmyk(60, 10, 65, 10),
            "weekend_color": make_cmyk(25, 45, 65, 15),
            "holiday_color": make_cmyk(0, 80, 75, 15),
            "background_color": make_cmyk(0, 0, 0, 0),
        },
    },
    {
        "id": "pal_juridico",
        "name": "Jurídico Bordô & Ouro",
        "description": "Elegância tradicional com bordô sóbrio e dourado fosco.",
        "colors": {
            "palette_name": "Jurídico Bordô & Ouro",
            "title_color": make_cmyk(20, 90, 75, 45),
            "weekday_color": make_cmyk(15, 55, 50, 35),
            "date_number_color": make_cmyk(25, 95, 80, 50),
            "ruling_line_color": make_cmyk(0, 5, 10, 25),
            "decorative_color": make_cmyk(20, 35, 80, 15),
            "highlight_color": make_cmyk(18, 38, 85, 12),
            "weekend_color": make_cmyk(15, 80, 65, 30),
            "holiday_color": make_cmyk(0, 95, 85, 15),
            "background_color": make_cmyk(0, 0, 0, 0),
        },
    },
    {
        "id": "pal_terracota",
        "name": "Moderno Terracota",
        "description": "Visual contemporâneo com terracota quente e marrom escuro.",
        "colors": {
            "palette_name": "Moderno Terracota",
            "title_color": make_cmyk(15, 75, 85, 25),
            "weekday_color": make_cmyk(20, 45, 55, 30),
            "date_number_color": make_cmyk(15, 80, 88, 28),
            "ruling_line_color": make_cmyk(0, 8, 12, 22),
            "decorative_color": make_cmyk(10, 50, 65, 10),
            "highlight_color": make_cmyk(12, 70, 90, 8),
            "weekend_color": make_cmyk(30, 55, 70, 20),
            "holiday_color": make_cmyk(0, 90, 85, 10),
            "background_color": make_cmyk(0, 0, 0, 0),
        },
    },
    {
        "id": "pal_tech",
        "name": "Corporativo Tech (Ciano)",
        "description": "Ciano gráfico limpo combinado com cinza chumbo.",
        "colors": {
            "palette_name": "Corporativo Tech (Ciano)",
            "title_color": make_cmyk(95, 35, 5, 15),
            "weekday_color": make_cmyk(60, 20, 10, 35),
            "date_number_color": make_cmyk(100, 40, 0, 20),
            "ruling_line_color": make_cmyk(10, 0, 0, 22),
            "decorative_color": make_cmyk(75, 15, 0, 5),
            "highlight_color": make_cmyk(85, 20, 0, 0),
            "weekend_color": make_cmyk(40, 65, 15, 10),
            "holiday_color": make_cmyk(0, 88, 80, 5),
            "background_color": make_cmyk(0, 0, 0, 0),
        },
    },
    {
        "id": "pal_rose",
        "name": "Rosé Editorial",
        "description": "Rosé delicado com contraste em marrom cacau.",
        "colors": {
            "palette_name": "Rosé Editorial",
            "title_color": make_cmyk(20, 65, 55, 25),
            "weekday_color": make_cmyk(15, 45, 45, 35),
            "date_number_color": make_cmyk(18, 70, 55, 20),
            "ruling_line_color": make_cmyk(0, 12, 10, 18),
            "decorative_color": make_cmyk(5, 48, 38, 5),
            "highlight_color": make_cmyk(5, 60, 45, 8),
            "weekend_color": make_cmyk(10, 70, 55, 15),
            "holiday_color": make_cmyk(0, 88, 70, 10),
            "background_color": make_cmyk(0, 0, 0, 0),
        },
    },
    {
        "id": "pal_oliva",
        "name": "Botânico Oliva",
        "description": "Verde oliva orgânico com detalhes em mostarda suave.",
        "colors": {
            "palette_name": "Botânico Oliva",
            "title_color": make_cmyk(55, 35, 85, 35),
            "weekday_color": make_cmyk(45, 30, 65, 25),
            "date_number_color": make_cmyk(60, 38, 88, 40),
            "ruling_line_color": make_cmyk(8, 5, 15, 20),
            "decorative_color": make_cmyk(35, 20, 65, 15),
            "highlight_color": make_cmyk(15, 35, 90, 10),
            "weekend_color": make_cmyk(20, 55, 85, 20),
            "holiday_color": make_cmyk(0, 85, 85, 15),
            "background_color": make_cmyk(0, 0, 0, 0),
        },
    },
]

MONTHLY_MOTIVATIONAL_PHRASES: list[str] = [
    "Janeiro: Grandes conquistas começam com disciplina diária e propósito claro.",
    "Fevereiro: Mantenha o foco no essencial e avance com consistência.",
    "Março: A organização transforma metas ambiciosas em resultados concretos.",
    "Abril: Pequenos progressos diários constroem grandes realizações.",
    "Maio: Excelência é um hábito cultivado em cada compromisso assumido.",
    "Junho: Metade do ano — revise seus planos, celebre avanços e ajuste a rota.",
    "Julho: Clareza de prioridades é a chave para uma rotina produtiva.",
    "Agosto: Persistência e planejamento superam qualquer desafio.",
    "Setembro: Renove suas ideias e execute seus projetos com energia.",
    "Outubro: Foco no processo, qualidade em cada entrega.",
    "Novembro: Consolide suas metas e prepare o terreno para o próximo ciclo.",
    "Dezembro: Gratidão pelas conquistas e visão estratégica para o novo ano.",
]

PHRASE_PACKS: list[dict[str, Any]] = [
    {
        "name": "Frases Executivas & Negócios",
        "phrases": [
            "Planejamento é trazer o futuro para o presente para agir agora.",
            "Qualidade é fazer certo mesmo quando ninguém está olhando.",
            "Resultados extraordinários nascem da constância diária.",
            "Cada dia é uma nova oportunidade de entregar excelência.",
        ],
    },
    {
        "name": "Bem-estar & Clínicas",
        "phrases": [
            "Cuidar de si mesmo é o primeiro passo para cuidar de tudo ao redor.",
            "Respire fundo, organize seu dia e respeite seu ritmo.",
            "Equilíbrio entre corpo, mente e rotina gera saúde verdadeira.",
        ],
    },
]


def get_template_catalog() -> list[dict[str, Any]]:
    """Retorna os 7 modelos prontos de miolo com configurações completas."""
    templates: list[dict[str, Any]] = []

    # 1. Diário (1DPP)
    c1 = default_project_config()
    c1["calendar"]["layout_mode"] = "1_dpp"
    c1["calendar"]["weekend_mode"] = "together"
    c1["ruling"]["ruling_type"] = "horizontal"
    c1["ruling"]["show_time_column"] = True
    templates.append(
        {
            "id": "diario",
            "name": "Diário 1 Dia por Página",
            "category": "Tradicional",
            "badge": "Mais Vendido",
            "description": "15x21 cm com 1 dia por página (Sáb/Dom juntos), horários das 7h às 21h e mini-calendário.",
            "config": c1,
        }
    )

    # 2. Permanente (Não datado)
    c2 = default_project_config()
    c2["calendar"]["is_dated"] = False
    c2["calendar"]["layout_mode"] = "1_dpp"
    c2["calendar"]["show_mini_calendar"] = False
    c2["special_pages"]["cover_title"] = "AGENDA PERMANENTE"
    c2["special_pages"]["cover_subtitle"] = "Uso Livre • Todos os Anos"
    c2["colors"] = copy.deepcopy(CMYK_PALETTES[2]["colors"])
    c2["ruling"]["line_color"] = copy.deepcopy(CMYK_PALETTES[2]["colors"]["ruling_line_color"])
    templates.append(
        {
            "id": "permanente",
            "name": "Agenda Permanente (Não Datada)",
            "category": "Permanente",
            "badge": "Sem Validade",
            "description": "366 dias sem ano fixo com marcador de dia da semana (D S T Q Q S S). Estoque válido o ano inteiro.",
            "config": c2,
        }
    )

    # 3. Semanal
    c3 = default_project_config()
    c3["calendar"]["layout_mode"] = "weekly"
    c3["calendar"]["week_starts_on"] = 1
    c3["ruling"]["show_time_column"] = False
    c3["ruling"]["line_spacing_mm"] = 5.5
    c3["colors"] = copy.deepcopy(CMYK_PALETTES[4]["colors"])
    c3["ruling"]["line_color"] = copy.deepcopy(CMYK_PALETTES[4]["colors"]["ruling_line_color"])
    templates.append(
        {
            "id": "semanal",
            "name": "Agenda Semanal Compacta",
            "category": "Compacta",
            "badge": "Econômica",
            "description": "Visão completa da semana em grade com área de metas semanais. Menor número de páginas e custo gráfico.",
            "config": c3,
        }
    )

    # 4. Mensal
    c4 = default_project_config()
    c4["calendar"]["layout_mode"] = "monthly"
    c4["ruling"]["ruling_type"] = "dotted"
    c4["ruling"]["line_spacing_mm"] = 5.0
    c4["ruling"]["show_time_column"] = False
    c4["colors"] = copy.deepcopy(CMYK_PALETTES[6]["colors"])
    c4["ruling"]["line_color"] = copy.deepcopy(CMYK_PALETTES[6]["colors"]["ruling_line_color"])
    templates.append(
        {
            "id": "mensal",
            "name": "Planner Mensal + Semanas",
            "category": "Planner",
            "badge": "Pontilhado",
            "description": "Visão mensal panorâmica em grade + planejamento semanal com pauta pontilhada editorial.",
            "config": c4,
        }
    )

    # 5. Financeiro
    c5 = default_project_config()
    c5["calendar"]["layout_mode"] = "financial"
    c5["special_pages"]["financial_summary"] = True
    c5["special_pages"]["cover_title"] = "CONTROLE FINANCEIRO"
    c5["special_pages"]["cover_subtitle"] = "Fluxo de Caixa Diário & Metas"
    c5["colors"] = copy.deepcopy(CMYK_PALETTES[3]["colors"])
    c5["ruling"]["line_color"] = copy.deepcopy(CMYK_PALETTES[3]["colors"]["ruling_line_color"])
    templates.append(
        {
            "id": "financeiro",
            "name": "Agenda Controle Financeiro",
            "category": "Negócios",
            "badge": "Fluxo de Caixa",
            "description": "Compromissos diários integrados a tabela de Entradas, Saídas, Saldo do Dia e Balanço Anual.",
            "config": c5,
        }
    )

    # 6. Empresarial
    c6 = default_project_config()
    c6["calendar"]["layout_mode"] = "corporate"
    c6["special_pages"]["cover_title"] = "AGENDA CORPORATIVA"
    c6["special_pages"]["cover_subtitle"] = "Gestão Executiva & Reuniões"
    c6["colors"] = copy.deepcopy(CMYK_PALETTES[5]["colors"])
    c6["ruling"]["line_color"] = copy.deepcopy(CMYK_PALETTES[5]["colors"]["ruling_line_color"])
    c6["footer"]["company_name"] = "Sua Empresa S.A."
    c6["footer"]["alignment"] = "split"
    templates.append(
        {
            "id": "empresarial",
            "name": "Agenda Empresarial Executiva",
            "category": "Corporativo",
            "badge": "B2B / Brindes",
            "description": "Top 3 Prioridades, Agenda de Reuniões por horário, coluna Delegar/Follow-up e rodapé institucional.",
            "config": c6,
        }
    )

    # 7. Planner
    c7 = default_project_config()
    c7["calendar"]["layout_mode"] = "planner"
    c7["ruling"]["ruling_type"] = "dotted"
    c7["ruling"]["line_spacing_mm"] = 5.5
    c7["colors"] = copy.deepcopy(CMYK_PALETTES[7]["colors"])
    c7["ruling"]["line_color"] = copy.deepcopy(CMYK_PALETTES[7]["colors"]["ruling_line_color"])
    c7["special_pages"]["cover_title"] = "PLANNER DIÁRIO"
    c7["special_pages"]["cover_subtitle"] = "Foco, Hábitos & Produtividade"
    templates.append(
        {
            "id": "planner",
            "name": "Planner Diário Produtividade",
            "category": "Planner",
            "badge": "Completo",
            "description": "Cronograma de horários + Bloco de Checklist de Tarefas + Área de Notas e Gratidão.",
            "config": c7,
        }
    )

    return templates


def build_config_from_template(template_id: str | None) -> dict[str, Any]:
    """Cria uma cópia completa da configuração de um dos 7 modelos ou do padrão."""
    catalog = {t["id"]: t["config"] for t in get_template_catalog()}
    if template_id and template_id in catalog:
        return copy.deepcopy(catalog[template_id])
    return default_project_config()


def _ensure_demo_svg_assets() -> None:
    """Cria selos e logotipo SVG vetoriais de exemplo em uploads/demo/."""
    demo_dir = UPLOADS_DIR / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)

    logo_svg = demo_dir / "logo_grafica_demo.svg"
    if not logo_svg.exists():
        logo_svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 50">'
            '<rect x="2" y="5" width="40" height="40" rx="8" fill="#1F3A5F"/>'
            '<circle cx="22" cy="25" r="10" fill="#D99B26"/>'
            '<rect x="52" y="12" width="120" height="8" rx="3" fill="#1F3A5F"/>'
            '<rect x="52" y="27" width="84" height="6" rx="3" fill="#5A6D82"/>'
            '</svg>',
            encoding="utf-8",
        )

    seal_svg = demo_dir / "selo_qualidade.svg"
    if not seal_svg.exists():
        seal_svg.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            '<circle cx="50" cy="50" r="44" fill="none" stroke="#1F3A5F" stroke-width="4"/>'
            '<circle cx="50" cy="50" r="34" fill="none" stroke="#D99B26" stroke-width="2"/>'
            '<polygon points="50,20 58,38 78,40 63,53 67,73 50,63 33,73 37,53 22,40 42,38" fill="#1F3A5F"/>'
            '</svg>',
            encoding="utf-8",
        )


def seed_initial_data(db: Session) -> None:
    """Popula paletas CMYK, frases, gráficos e um projeto exemplo caso o banco esteja vazio."""
    _ensure_demo_svg_assets()

    if db.query(LibraryItem).count() == 0:
        for pal in CMYK_PALETTES:
            db.add(
                LibraryItem(
                    category="palette",
                    name=pal["name"],
                    description=pal["description"],
                    tags="cmyk,paleta,cores",
                    content_json=json.dumps(pal["colors"], ensure_ascii=False),
                    is_system=1,
                )
            )
        for idx, phrase in enumerate(MONTHLY_MOTIVATIONAL_PHRASES, start=1):
            db.add(
                LibraryItem(
                    category="phrase",
                    name=f"Frase Motivacional - Mês {idx:02d}",
                    description="Frase pronta para abertura mensal",
                    tags="motivacional,mensal",
                    content_json=json.dumps({"text": phrase, "month": idx}, ensure_ascii=False),
                    is_system=1,
                )
            )
        for pack in PHRASE_PACKS:
            for p_idx, p_txt in enumerate(pack["phrases"], start=1):
                db.add(
                    LibraryItem(
                        category="phrase",
                        name=f"{pack['name']} #{p_idx}",
                        description=pack["name"],
                        tags="corporativo,frase",
                        content_json=json.dumps({"text": p_txt}, ensure_ascii=False),
                        is_system=1,
                    )
                )
        db.add(
            LibraryItem(
                category="logo",
                name="Logotipo Corporativo Exemplo (SVG)",
                description="Logotipo vetorial de demonstração em SVG",
                tags="logo,svg,demo",
                content_json=json.dumps({"url": "/uploads/demo/logo_grafica_demo.svg"}),
                file_path="/uploads/demo/logo_grafica_demo.svg",
                is_system=1,
            )
        )
        db.add(
            LibraryItem(
                category="graphic",
                name="Selo Estrela Editorial (SVG)",
                description="Elemento decorativo vetorial para capas e aberturas",
                tags="selo,svg,grafico",
                content_json=json.dumps({"url": "/uploads/demo/selo_qualidade.svg"}),
                file_path="/uploads/demo/selo_qualidade.svg",
                is_system=1,
            )
        )
        db.commit()

    if db.query(Project).count() == 0:
        demo_cfg = build_config_from_template("diario")
        demo_cfg["footer"]["company_name"] = "Gráfica Modelo & Brindes"
        demo_cfg["footer"]["professional_name"] = "Edição Exclusiva 2026"
        demo_cfg["footer"]["logo_url"] = "/uploads/demo/logo_grafica_demo.svg"
        demo_cfg["footer"]["alignment"] = "split"
        demo_cfg["elements"] = [
            {
                "id": "el_demo_quote_1",
                "type": "phrase",
                "label": "Frase Motivacional Rodapé",
                "text": "“Organização diária é o caminho mais curto para grandes conquistas.”",
                "image_url": "",
                "shape_type": "rect",
                "x_mm": 20.0,
                "y_mm": 182.0,
                "width_mm": 110.0,
                "height_mm": 11.0,
                "rotation_deg": 0.0,
                "font_family": "Georgia",
                "font_size_pt": 8.5,
                "bold": False,
                "italic": True,
                "underline": False,
                "alignment": "center",
                "color": make_cmyk(75, 55, 25, 25),
                "bg_color": None,
                "border_color": None,
                "border_width_pt": 0.0,
                "opacity": 0.9,
                "z_index": 10,
                "locked": False,
                "target_rule": "daily_only",
                "target_pages": "",
                "target_weekdays": [],
                "target_dates": [],
                "target_months": [],
            },
            {
                "id": "el_demo_month_1",
                "type": "phrase",
                "label": "Frase de Abertura ({{MES}})",
                "text": "{{MES}} — Planeje com clareza, execute com consistência.",
                "image_url": "",
                "shape_type": "rect",
                "x_mm": 20.0,
                "y_mm": 112.0,
                "width_mm": 110.0,
                "height_mm": 12.0,
                "rotation_deg": 0.0,
                "font_family": "Georgia",
                "font_size_pt": 10.5,
                "bold": True,
                "italic": True,
                "underline": False,
                "alignment": "center",
                "color": make_cmyk(15, 45, 90, 5),
                "bg_color": None,
                "border_color": None,
                "border_width_pt": 0.0,
                "opacity": 1.0,
                "z_index": 11,
                "locked": False,
                "target_rule": "month_openers",
                "target_pages": "",
                "target_weekdays": [],
                "target_dates": [],
                "target_months": [],
            },
        ]
        gen = generate_agenda_pages(demo_cfg)
        db.add(
            Project(
                name="Agenda Executiva 2026 - Modelo Demonstração",
                client_name="Cliente Exemplo Ltda",
                description="Projeto demonstrativo 15x21 cm (A5) com 1 dia por página, CMYK e frases automáticas.",
                year=2026,
                template_type="diario",
                format_name="15 x 21 cm (A5)",
                config_json=json.dumps(demo_cfg, ensure_ascii=False),
                page_count=gen["total_pages"],
                is_favorite=1,
            )
        )
        db.commit()
