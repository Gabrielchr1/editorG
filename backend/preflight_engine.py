"""Motor de Pré-Impressão (Preflight) profissional para conferência gráfica."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image

from backend.calendar_engine import generate_agenda_pages
from backend.pdf_engine import _resolve_upload_path, get_available_fonts


def _rotated_bbox(x: float, y: float, w: float, h: float, deg: float) -> tuple[float, float, float, float]:
    """Calcula a caixa envolvente (min_x, min_y, max_x, max_y) em mm de um retângulo rotacionado."""
    cx = x + w / 2.0
    cy = y + h / 2.0
    rad = math.radians(deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    hw, hh = w / 2.0, h / 2.0
    corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    xs, ys = [], []
    for dx, dy in corners:
        rx = cx + dx * cos_a - dy * sin_a
        ry = cy + dx * sin_a + dy * cos_a
        xs.append(rx)
        ys.append(ry)
    return (min(xs), min(ys), max(xs), max(ys))


def run_preflight(config: dict[str, Any]) -> dict[str, Any]:
    """Executa análise completa de pré-impressão sobre o projeto e retorna relatório."""
    checks: list[dict[str, Any]] = []
    warnings_count = 0
    errors_count = 0

    def add_check(code: str, category: str, status: str, title: str, detail: str, fix_hint: str = "") -> None:
        nonlocal warnings_count, errors_count
        if status == "warning":
            warnings_count += 1
        elif status == "error":
            errors_count += 1
        checks.append(
            {
                "code": code,
                "category": category,
                "status": status,  # "ok" | "warning" | "error" | "info"
                "title": title,
                "detail": detail,
                "fix_hint": fix_hint,
            }
        )

    ps = config.get("page_setup", {})
    base_w = float(ps.get("width_mm", 150.0))
    base_h = float(ps.get("height_mm", 210.0))
    if ps.get("orientation", "portrait") == "landscape":
        trim_w, trim_h = max(base_w, base_h), min(base_w, base_h)
    else:
        trim_w, trim_h = min(base_w, base_h), max(base_w, base_h)

    bleed = float(ps.get("bleed_mm", 3.0))
    safety = float(ps.get("safety_margin_mm", 5.0))
    m_inner = float(ps.get("margin_inner_mm", 18.0))
    m_outer = float(ps.get("margin_outer_mm", 10.0))
    m_top = float(ps.get("margin_top_mm", 12.0))
    m_bottom = float(ps.get("margin_bottom_mm", 12.0))
    mirror = bool(ps.get("mirror_margins", True))

    # 1. Dimensões e Sangria
    add_check(
        "DIMENSIONS",
        "Formato",
        "ok",
        f"Formato final {trim_w:.1f} x {trim_h:.1f} mm ({trim_w / 10:.1f} x {trim_h / 10:.1f} cm)",
        f"Orientação {'Retrato' if trim_h >= trim_w else 'Paisagem'}, medidas reais configuradas em milímetros.",
    )

    if bleed < 2.0:
        add_check(
            "BLEED_LOW",
            "Sangria",
            "warning",
            f"Sangria reduzida ({bleed:.1f} mm)",
            "Gráficas recomendam ao menos 3,0 mm de sangria para evitar filetes brancos após o refilo.",
            "Ajuste a sangria para 3,0 mm na aba Formato & Margens.",
        )
    else:
        add_check(
            "BLEED_OK",
            "Sangria",
            "ok",
            f"Sangria configurada: {bleed:.1f} mm",
            f"Dimensão bruta com sangria: {trim_w + 2 * bleed:.1f} x {trim_h + 2 * bleed:.1f} mm.",
        )

    # 2. Encadernação e Margens
    if m_inner < 14.0:
        add_check(
            "GUTTER_LOW",
            "Encadernação",
            "warning",
            f"Margem interna reduzida ({m_inner:.1f} mm)",
            "Para encadernação Wire-o, Espiral ou Brochura, recomenda-se margem interna >= 15 mm para não perfurar texto.",
            "Aumente a margem interna para 18 mm.",
        )
    else:
        add_check(
            "GUTTER_OK",
            "Encadernação",
            "ok",
            f"Margem interna para encadernação: {m_inner:.1f} mm",
            f"Margens espelhadas pares/ímpares: {'Ativado' if mirror else 'Desativado'} | Externa: {m_outer:.1f} mm | Sup/Inf: {m_top:.1f}/{m_bottom:.1f} mm.",
        )

    # 3. Área de Segurança e Posicionamento de Elementos
    out_of_safety: list[dict[str, Any]] = []
    out_of_trim: list[dict[str, Any]] = []
    for el in config.get("elements", []):
        x = float(el.get("x_mm", 0.0))
        y = float(el.get("y_mm", 0.0))
        w = float(el.get("width_mm", 10.0))
        h = float(el.get("height_mm", 10.0))
        rot = float(el.get("rotation_deg", 0.0))
        min_x, min_y, max_x, max_y = _rotated_bbox(x, y, w, h, rot)
        label = el.get("label") or (el.get("text") or "")[:30] or el.get("id")
        if min_x < 0 or min_y < 0 or max_x > trim_w or max_y > trim_h:
            out_of_trim.append({"id": el.get("id"), "label": label, "bbox": [round(min_x, 1), round(min_y, 1), round(max_x, 1), round(max_y, 1)]})
        elif min_x < safety or min_y < safety or max_x > (trim_w - safety) or max_y > (trim_h - safety):
            out_of_safety.append({"id": el.get("id"), "label": label, "bbox": [round(min_x, 1), round(min_y, 1), round(max_x, 1), round(max_y, 1)]})

    if out_of_trim:
        add_check(
            "ELEMENTS_OUT_OF_TRIM",
            "Posicionamento",
            "error",
            f"{len(out_of_trim)} elemento(s) ultrapassam o limite físico da página",
            "Elementos fora da linha de corte: " + ", ".join(item["label"] for item in out_of_trim),
            "Reposicione os elementos para dentro da área de segurança.",
        )
    elif out_of_safety:
        add_check(
            "ELEMENTS_OUT_OF_SAFETY",
            "Posicionamento",
            "warning",
            f"{len(out_of_safety)} elemento(s) invadem a área de segurança ({safety:.1f} mm)",
            "Elementos próximos ao corte: " + ", ".join(item["label"] for item in out_of_safety),
            "Mova os elementos para dentro do retângulo da área de segurança.",
        )
    else:
        add_check(
            "ELEMENTS_POSITION_OK",
            "Posicionamento",
            "ok",
            f"Todos os {len(config.get('elements', []))} elementos estão dentro da área de segurança",
            f"Área segura verificada ({safety:.1f} mm das bordas).",
        )

    # Rodapé vs Área de Segurança
    footer = config.get("footer", {})
    if footer.get("enabled", True):
        f_dist = float(footer.get("distance_from_bottom_mm", 8.0))
        if f_dist < safety:
            add_check(
                "FOOTER_SAFETY",
                "Rodapé",
                "warning",
                f"Rodapé muito próximo à borda inferior ({f_dist:.1f} mm < {safety:.1f} mm)",
                "O texto ou logotipo do rodapé pode ficar próximo demais do refilo.",
                f"Aumente a distância inferior para pelo menos {safety:.1f} mm.",
            )
        else:
            add_check(
                "FOOTER_OK",
                "Rodapé",
                "ok",
                "Posicionamento do rodapé aprovado",
                f"Distância inferior de {f_dist:.1f} mm (dentro da área segura).",
            )

    # 4. Cores CMYK e Carga Total de Tinta (TAC)
    colors = config.get("colors", {})
    high_tac: list[str] = []
    for k_name, c_dict in colors.items():
        if isinstance(c_dict, dict) and "c" in c_dict:
            tac = int(c_dict.get("c", 0)) + int(c_dict.get("m", 0)) + int(c_dict.get("y", 0)) + int(c_dict.get("k", 0))
            if tac > 300:
                high_tac.append(f"{k_name} ({tac}%)")

    ruling_col = config.get("ruling", {}).get("line_color") or colors.get("ruling_line_color", {})
    ruling_tac = sum(int(ruling_col.get(ch, 0)) for ch in ("c", "m", "y", "k")) if isinstance(ruling_col, dict) else 25

    if high_tac:
        add_check(
            "CMYK_HIGH_TAC",
            "Cores CMYK",
            "warning",
            "Carga total de tinta (TAC) acima de 300%",
            "Cores muito carregadas: " + ", ".join(high_tac) + ". Podem borrar na impressão.",
            "Reduza a soma C+M+Y+K para no máximo 280%-300%.",
        )
    elif ruling_tac < 8 and config.get("ruling", {}).get("ruling_type") != "blank":
        add_check(
            "RULING_LIGHT",
            "Cores CMYK",
            "warning",
            f"Linhas de pauta muito claras (tinta total {ruling_tac}%)",
            "Linhas com menos de 8% de tinta podem falhar em impressoras laser/offset.",
            "Recomenda-se ao menos 15%-25% de Preto (K) nas linhas da pauta.",
        )
    else:
        add_check(
            "CMYK_OK",
            "Cores CMYK",
            "ok",
            "Perfil de cores 100% CMYK verificado",
            "Todas as cores estão dentro dos limites gráficos de carga de tinta (TAC <= 300%).",
        )

    # 5. Imagens e Logotipos (DPI)
    asset_urls: list[tuple[str, str, float, float]] = []
    if footer.get("enabled") and footer.get("logo_url"):
        asset_urls.append(("Logotipo do Rodapé", footer["logo_url"], float(footer.get("logo_width_mm", 22.0)), float(footer.get("logo_height_mm", 10.0))))
    for el in config.get("elements", []):
        if el.get("type") == "image" and el.get("image_url"):
            asset_urls.append((el.get("label") or "Imagem no Canvas", el["image_url"], float(el.get("width_mm", 30.0)), float(el.get("height_mm", 20.0))))

    if not asset_urls:
        add_check("ASSETS_NONE", "Imagens", "info", "Nenhuma imagem raster inserida", "Todo o miolo será renderizado em vetores puros.")
    else:
        for label, url, w_mm, h_mm in asset_urls:
            p = _resolve_upload_path(url)
            if not p:
                add_check("ASSET_MISSING", "Imagens", "error", f"Arquivo não encontrado: {label}", f"Caminho ausente: {url}", "Reenvie o logotipo ou imagem.")
                continue
            ext = p.suffix.lower()
            if ext == ".svg":
                add_check("ASSET_SVG", "Imagens", "ok", f"{label}: Vetor SVG", "Gráfico vetorial com nitidez infinita na impressão.")
            elif ext == ".pdf":
                add_check("ASSET_PDF", "Imagens", "warning", f"{label}: Arquivo PDF anexado", "Para incorporação direta no miolo sem perda vetorial, prefira exportar o logotipo em SVG ou PNG 300 DPI.")
            else:
                try:
                    with Image.open(p) as im:
                        px_w, px_h = im.size
                    dpi_x = px_w / max(0.01, w_mm / 25.4)
                    dpi_y = px_h / max(0.01, h_mm / 25.4)
                    eff_dpi = min(dpi_x, dpi_y)
                    if eff_dpi < 150:
                        add_check(
                            "ASSET_LOW_DPI",
                            "Imagens",
                            "error",
                            f"{label}: Resolução baixa ({eff_dpi:.0f} DPI)",
                            f"Arquivo {px_w}x{px_h}px impresso em {w_mm:.1f}x{h_mm:.1f}mm resulta em menos de 150 DPI.",
                            "Envie uma imagem com pelo menos 300 DPI ou reduza as dimensões no layout.",
                        )
                    elif eff_dpi < 300:
                        add_check(
                            "ASSET_MED_DPI",
                            "Imagens",
                            "warning",
                            f"{label}: Resolução média ({eff_dpi:.0f} DPI)",
                            f"Recomendado 300 DPI para impressão offset/digital fina ({px_w}x{px_h}px).",
                        )
                    else:
                        add_check(
                            "ASSET_OK_DPI",
                            "Imagens",
                            "ok",
                            f"{label}: {eff_dpi:.0f} DPI (Alta qualidade)",
                            f"Dimensões {px_w}x{px_h}px adequadas para impressão.",
                        )
                except Exception as exc:
                    add_check("ASSET_READ_ERR", "Imagens", "error", f"Erro ao ler {label}", str(exc))

    # 6. Fontes e Paginação
    avail_fonts = set(get_available_fonts())
    used_fonts = {
        config.get("export", {}).get("header_font_family", "Georgia"),
        config.get("export", {}).get("body_font_family", "Arial"),
        footer.get("font_family", "Arial"),
    }
    for el in config.get("elements", []):
        if el.get("type") == "phrase" and el.get("font_family"):
            used_fonts.add(el["font_family"])
    missing_fonts = [f for f in used_fonts if f not in avail_fonts]
    if missing_fonts:
        add_check(
            "FONTS_FALLBACK",
            "Fontes",
            "warning",
            "Fontes com substituição automática",
            f"Fontes não encontradas localmente serão convertidas para Arial/Helvetica: {', '.join(missing_fonts)}.",
        )
    else:
        add_check(
            "FONTS_OK",
            "Fontes",
            "ok",
            f"{len(used_fonts)} família(s) de fontes TrueType prontas para incorporação",
            "Todas as fontes selecionadas serão incorporadas vetorialmente no PDF.",
        )

    # Paginação
    try:
        cal_res = generate_agenda_pages(config)
        total_pages = cal_res["total_pages"]
        total_sheets = cal_res["total_sheets"]
        add_check(
            "PAGINATION",
            "Paginação",
            "ok",
            f"{total_pages} páginas geradas ({total_sheets} folhas frente e verso)",
            f"Modo: {cal_res['layout_mode']} | Dias gerados: {cal_res['total_days']}."
            + (" Paginação par (pronta para impressão frente e verso)." if total_pages % 2 == 0 else " Paginação ímpar (último verso em branco na encadernação)."),
        )
    except Exception as exc:
        total_pages = 0
        total_sheets = 0
        add_check("CALENDAR_ERR", "Calendário", "error", "Erro na configuração de datas", str(exc))

    overall = "error" if errors_count > 0 else ("warning" if warnings_count > 0 else "ok")
    return {
        "status": overall,
        "errors": errors_count,
        "warnings": warnings_count,
        "total_pages": total_pages,
        "total_sheets": total_sheets,
        "out_of_safety": out_of_safety,
        "out_of_trim": out_of_trim,
        "checks": checks,
    }
