"""Motor profissional de geração de PDF para impressão em CMYK nativo."""

from __future__ import annotations

import io
import os
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import (
    Circle as RL_Circle,
    Drawing as RL_Drawing,
    Ellipse as RL_Ellipse,
    Group as RL_Group,
    Line as RL_Line,
    Path as RL_Path,
    Polygon as RL_Polygon,
    PolyLine as RL_PolyLine,
    Rect as RL_Rect,
)
from reportlab.lib.colors import CMYKColor
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from backend.calendar_engine import (
    MONTH_NAMES_PT,
    WEEKDAY_NAMES_PT,
    WEEKDAY_SHORT_PT,
    generate_agenda_pages,
    parse_page_list,
)

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
WINDOWS_FONTS_DIR = Path("C:/Windows/Fonts")
LINUX_FONT_DIRS = [Path("/usr/share/fonts"), Path("/usr/local/share/fonts")]

_LIBERATION_SANS = {
    "regular": "liberationsans-regular.ttf",
    "bold": "liberationsans-bold.ttf",
    "italic": "liberationsans-italic.ttf",
    "bold_italic": "liberationsans-bolditalic.ttf",
}
_LIBERATION_SERIF = {
    "regular": "liberationserif-regular.ttf",
    "bold": "liberationserif-bold.ttf",
    "italic": "liberationserif-italic.ttf",
    "bold_italic": "liberationserif-bolditalic.ttf",
}
_LIBERATION_MONO = {
    "regular": "liberationmono-regular.ttf",
    "bold": "liberationmono-bold.ttf",
    "italic": "liberationmono-italic.ttf",
    "bold_italic": "liberationmono-bolditalic.ttf",
}
_DEJAVU_SANS = {
    "regular": "dejavusans.ttf",
    "bold": "dejavusans-bold.ttf",
    "italic": "dejavusans-oblique.ttf",
    "bold_italic": "dejavusans-boldoblique.ttf",
}
_DEJAVU_SERIF = {
    "regular": "dejavuserif.ttf",
    "bold": "dejavuserif-bold.ttf",
    "italic": "dejavuserif-italic.ttf",
    "bold_italic": "dejavuserif-bolditalic.ttf",
}

LINUX_FONT_FALLBACKS: dict[str, list[dict[str, str]]] = {
    "Arial": [_LIBERATION_SANS, _DEJAVU_SANS],
    "Calibri": [_LIBERATION_SANS, _DEJAVU_SANS],
    "Verdana": [_DEJAVU_SANS, _LIBERATION_SANS],
    "Trebuchet MS": [_LIBERATION_SANS, _DEJAVU_SANS],
    "Segoe UI": [_DEJAVU_SANS, _LIBERATION_SANS],
    "Tahoma": [_DEJAVU_SANS, _LIBERATION_SANS],
    "Times New Roman": [_LIBERATION_SERIF, _DEJAVU_SERIF],
    "Georgia": [_DEJAVU_SERIF, _LIBERATION_SERIF],
    "Garamond": [_LIBERATION_SERIF, _DEJAVU_SERIF],
    "Palatino": [_LIBERATION_SERIF, _DEJAVU_SERIF],
    "Courier New": [_LIBERATION_MONO],
}

FONT_CATALOG: dict[str, dict[str, str]] = {
    "Arial": {
        "regular": "arial.ttf",
        "bold": "arialbd.ttf",
        "italic": "ariali.ttf",
        "bold_italic": "arialbi.ttf",
    },
    "Times New Roman": {
        "regular": "times.ttf",
        "bold": "timesbd.ttf",
        "italic": "timesi.ttf",
        "bold_italic": "timesbi.ttf",
    },
    "Georgia": {
        "regular": "georgia.ttf",
        "bold": "georgiab.ttf",
        "italic": "georgiai.ttf",
        "bold_italic": "georgiabi.ttf",
    },
    "Garamond": {
        "regular": "gara.ttf",
        "bold": "garabd.ttf",
        "italic": "garait.ttf",
        "bold_italic": "garabd.ttf",
    },
    "Palatino": {
        "regular": "pala.ttf",
        "bold": "palab.ttf",
        "italic": "palai.ttf",
        "bold_italic": "palabi.ttf",
    },
    "Verdana": {
        "regular": "verdana.ttf",
        "bold": "verdanab.ttf",
        "italic": "verdanai.ttf",
        "bold_italic": "verdanaz.ttf",
    },
    "Trebuchet MS": {
        "regular": "trebuc.ttf",
        "bold": "trebucbd.ttf",
        "italic": "trebucit.ttf",
        "bold_italic": "trebucbi.ttf",
    },
    "Calibri": {
        "regular": "calibri.ttf",
        "bold": "calibrib.ttf",
        "italic": "calibrii.ttf",
        "bold_italic": "calibribi.ttf",
    },
    "Courier New": {
        "regular": "cour.ttf",
        "bold": "courbd.ttf",
        "italic": "couri.ttf",
        "bold_italic": "courbi.ttf",
    },
    "Segoe UI": {
        "regular": "segoeui.ttf",
        "bold": "segoeuib.ttf",
        "italic": "segoeuii.ttf",
        "bold_italic": "segoeuiz.ttf",
    },
    "Tahoma": {
        "regular": "TAHOMA.TTF",
        "bold": "TAHOMABD.TTF",
        "italic": "TAHOMA.TTF",
        "bold_italic": "TAHOMABD.TTF",
    },
}

_FONTS_INITIALIZED = False
_REGISTERED_FAMILIES: dict[str, dict[str, str]] = {}


def ensure_fonts_registered() -> dict[str, dict[str, str]]:
    """Registra fontes TrueType do sistema (Windows e Linux) no ReportLab (apenas uma vez)."""
    global _FONTS_INITIALIZED, _REGISTERED_FAMILIES
    if _FONTS_INITIALIZED:
        return _REGISTERED_FAMILIES

    font_files_map: dict[str, Path] = {}
    if WINDOWS_FONTS_DIR.exists():
        for p in WINDOWS_FONTS_DIR.iterdir():
            if p.suffix.lower() == ".ttf":
                font_files_map[p.name.lower()] = p
    for linux_dir in LINUX_FONT_DIRS:
        if linux_dir.exists():
            for p in linux_dir.rglob("*"):
                if p.is_file() and p.suffix.lower() == ".ttf":
                    font_files_map.setdefault(p.name.lower(), p)

    for family, variants in FONT_CATALOG.items():
        candidate_sets = [variants] + LINUX_FONT_FALLBACKS.get(family, [])
        active_variants = None
        reg_path = None
        for cand in candidate_sets:
            cand_path = font_files_map.get(cand["regular"].lower())
            if cand_path:
                active_variants = cand
                reg_path = cand_path
                break
        if not reg_path or not active_variants:
            continue
        fam_map: dict[str, str] = {}
        try:
            reg_name = f"EG_{family.replace(' ', '_')}_Regular"
            pdfmetrics.registerFont(TTFont(reg_name, str(reg_path)))
            fam_map["regular"] = reg_name

            for style_key in ("bold", "italic", "bold_italic"):
                v_file = active_variants.get(style_key, "").lower()
                v_path = font_files_map.get(v_file) or reg_path
                v_name = f"EG_{family.replace(' ', '_')}_{style_key}"
                if v_path == reg_path and style_key != "regular":
                    fam_map[style_key] = reg_name
                else:
                    pdfmetrics.registerFont(TTFont(v_name, str(v_path)))
                    fam_map[style_key] = v_name

            pdfmetrics.registerFontFamily(
                family,
                normal=fam_map["regular"],
                bold=fam_map["bold"],
                italic=fam_map["italic"],
                boldItalic=fam_map["bold_italic"],
            )
            _REGISTERED_FAMILIES[family] = fam_map
        except Exception:
            continue

    _FONTS_INITIALIZED = True
    return _REGISTERED_FAMILIES


def resolve_font(family: str, bold: bool = False, italic: bool = False) -> str:
    """Resolve família + estilo para o nome exato da fonte registrada no ReportLab."""
    families = ensure_fonts_registered()
    if family == "Helvetica" and "Arial" in families and family not in families:
        # Mantém Helvetica disponível nativamente se o usuário escolher explicitamente
        if bold and italic:
            return "Helvetica-BoldOblique"
        if bold:
            return "Helvetica-Bold"
        if italic:
            return "Helvetica-Oblique"
        return "Helvetica"

    if family in families:
        m = families[family]
        if bold and italic:
            return m.get("bold_italic", m["regular"])
        if bold:
            return m.get("bold", m["regular"])
        if italic:
            return m.get("italic", m["regular"])
        return m["regular"]

    if "Arial" in families:
        m = families["Arial"]
        if bold and italic:
            return m.get("bold_italic", m["regular"])
        if bold:
            return m.get("bold", m["regular"])
        if italic:
            return m.get("italic", m["regular"])
        return m["regular"]

    if bold and italic:
        return "Helvetica-BoldOblique"
    if bold:
        return "Helvetica-Bold"
    if italic:
        return "Helvetica-Oblique"
    return "Helvetica"


def get_available_fonts() -> list[str]:
    """Retorna lista de famílias de fontes disponíveis para impressão."""
    families = ensure_fonts_registered()
    available = list(families.keys())
    if "Helvetica" not in available:
        available.append("Helvetica")
    return available


def to_cmyk(color_dict: dict[str, Any] | None, alpha: float = 1.0, fallback_k: int = 100) -> CMYKColor:
    """Converte dicionário CMYK (0..100) para CMYKColor nativo do ReportLab."""
    if not color_dict:
        return CMYKColor(0, 0, 0, fallback_k / 100.0, alpha=alpha)
    c_val = max(0.0, min(100.0, float(color_dict.get("c", 0)))) / 100.0
    m_val = max(0.0, min(100.0, float(color_dict.get("m", 0)))) / 100.0
    y_val = max(0.0, min(100.0, float(color_dict.get("y", 0)))) / 100.0
    k_val = max(0.0, min(100.0, float(color_dict.get("k", 0)))) / 100.0
    return CMYKColor(c_val, m_val, y_val, k_val, alpha=alpha)


def tint_cmyk(color_dict: dict[str, Any] | None, factor: float = 0.15) -> CMYKColor:
    """Retorna versão atenuada (retícula em %) da mesma cor CMYK."""
    if not color_dict:
        return CMYKColor(0, 0, 0, 0.1 * factor)
    f = max(0.0, min(1.0, factor))
    c_val = max(0.0, min(100.0, float(color_dict.get("c", 0)))) / 100.0 * f
    m_val = max(0.0, min(100.0, float(color_dict.get("m", 0)))) / 100.0 * f
    y_val = max(0.0, min(100.0, float(color_dict.get("y", 0)))) / 100.0 * f
    k_val = max(0.0, min(100.0, float(color_dict.get("k", 0)))) / 100.0 * f
    return CMYKColor(c_val, m_val, y_val, k_val)


def _resolve_upload_path(url_or_path: str) -> Path | None:
    if not url_or_path:
        return None
    cleaned = url_or_path.strip()
    if cleaned.startswith("/uploads/"):
        candidate = UPLOADS_DIR / cleaned[len("/uploads/"):]
        return candidate if candidate.exists() and candidate.is_file() else None
    if cleaned.startswith("uploads/"):
        candidate = BASE_DIR / cleaned
        return candidate if candidate.exists() and candidate.is_file() else None
    p = Path(cleaned)
    if p.exists() and p.is_file():
        return p
    candidate2 = UPLOADS_DIR / p.name
    return candidate2 if candidate2.exists() and candidate2.is_file() else None


def _parse_svg_color(val: str | None) -> CMYKColor | None:
    if not val or val.strip().lower() in ("none", "transparent"):
        return None
    s = val.strip()
    if s.startswith("#") and len(s) in (4, 7):
        if len(s) == 4:
            s = "#" + "".join(ch * 2 for ch in s[1:])
        r = int(s[1:3], 16) / 255.0
        g = int(s[3:5], 16) / 255.0
        b = int(s[5:7], 16) / 255.0
        k = 1.0 - max(r, g, b)
        if k >= 0.999:
            return CMYKColor(0, 0, 0, 1)
        return CMYKColor((1 - r - k) / (1 - k), (1 - g - k) / (1 - k), (1 - b - k) / (1 - k), k)
    named = {
        "black": CMYKColor(0, 0, 0, 1),
        "white": CMYKColor(0, 0, 0, 0),
        "red": CMYKColor(0, 1, 1, 0),
        "blue": CMYKColor(1, 0.7, 0, 0),
        "green": CMYKColor(0.8, 0, 0.9, 0.2),
        "gray": CMYKColor(0, 0, 0, 0.5),
        "grey": CMYKColor(0, 0, 0, 0.5),
    }
    return named.get(s.lower(), CMYKColor(0, 0, 0, 0.8))


def _parse_svg_path_d(d_str: str, path_obj: RL_Path) -> None:
    """Parser leve de comandos SVG path (M, L, H, V, C, Q, Z) para ReportLab Path."""
    tokens = re.findall(r"[A-Za-z]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", d_str or "")
    idx = 0
    cmd = ""
    cx, cy = 0.0, 0.0
    sx, sy = 0.0, 0.0

    def next_f() -> float:
        nonlocal idx
        val = float(tokens[idx])
        idx += 1
        return val

    while idx < len(tokens):
        t = tokens[idx]
        if t.isalpha():
            cmd = t
            idx += 1
            if cmd in ("Z", "z"):
                path_obj.closePath()
                cx, cy = sx, sy
            continue

        if cmd == "M":
            cx, cy = next_f(), next_f()
            sx, sy = cx, cy
            path_obj.moveTo(cx, cy)
            cmd = "L"
        elif cmd == "m":
            cx += next_f()
            cy += next_f()
            sx, sy = cx, cy
            path_obj.moveTo(cx, cy)
            cmd = "l"
        elif cmd == "L":
            cx, cy = next_f(), next_f()
            path_obj.lineTo(cx, cy)
        elif cmd == "l":
            cx += next_f()
            cy += next_f()
            path_obj.lineTo(cx, cy)
        elif cmd == "H":
            cx = next_f()
            path_obj.lineTo(cx, cy)
        elif cmd == "h":
            cx += next_f()
            path_obj.lineTo(cx, cy)
        elif cmd == "V":
            cy = next_f()
            path_obj.lineTo(cx, cy)
        elif cmd == "v":
            cy += next_f()
            path_obj.lineTo(cx, cy)
        elif cmd == "C":
            x1, y1, x2, y2, x3, y3 = next_f(), next_f(), next_f(), next_f(), next_f(), next_f()
            path_obj.curveTo(x1, y1, x2, y2, x3, y3)
            cx, cy = x3, y3
        elif cmd == "c":
            x1, y1 = cx + next_f(), cy + next_f()
            x2, y2 = cx + next_f(), cy + next_f()
            x3, y3 = cx + next_f(), cy + next_f()
            path_obj.curveTo(x1, y1, x2, y2, x3, y3)
            cx, cy = x3, y3
        elif cmd == "Q":
            x1, y1, x2, y2 = next_f(), next_f(), next_f(), next_f()
            # Converte quadrática para cúbica
            c1x = cx + (2 / 3) * (x1 - cx)
            c1y = cy + (2 / 3) * (y1 - cy)
            c2x = x2 + (2 / 3) * (x1 - x2)
            c2y = y2 + (2 / 3) * (y1 - y2)
            path_obj.curveTo(c1x, c1y, c2x, c2y, x2, y2)
            cx, cy = x2, y2
        elif cmd == "q":
            x1, y1 = cx + next_f(), cy + next_f()
            x2, y2 = cx + next_f(), cy + next_f()
            c1x = cx + (2 / 3) * (x1 - cx)
            c1y = cy + (2 / 3) * (y1 - cy)
            c2x = x2 + (2 / 3) * (x1 - x2)
            c2y = y2 + (2 / 3) * (y1 - y2)
            path_obj.curveTo(c1x, c1y, c2x, c2y, x2, y2)
            cx, cy = x2, y2
        else:
            idx += 1


def _build_svg_drawing(svg_path: Path) -> tuple[RL_Drawing, float, float] | None:
    """Converte SVG básico em Drawing vetorial do ReportLab em CMYK."""
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        vb = root.attrib.get("viewBox")
        if vb:
            parts = [float(x) for x in re.split(r"[\s,]+", vb.strip()) if x]
            vx, vy, vw, vh = parts[0], parts[1], parts[2], parts[3]
        else:
            vx, vy = 0.0, 0.0
            vw = float(re.sub(r"[^0-9.]", "", root.attrib.get("width", "100")) or 100)
            vh = float(re.sub(r"[^0-9.]", "", root.attrib.get("height", "100")) or 100)

        drawing = RL_Drawing(vw, vh)
        # Inverte eixo Y para coordenadas SVG (topo -> base)
        grp = RL_Group(transform=(1, 0, 0, -1, -vx, vh + vy))

        def walk(node: ET.Element, inherited_fill=None, inherited_stroke=None, inherited_sw=1.0) -> None:
            tag = node.tag.split("}")[-1].lower()
            fill_attr = node.attrib.get("fill")
            stroke_attr = node.attrib.get("stroke")
            sw_attr = node.attrib.get("stroke-width")

            fill_col = _parse_svg_color(fill_attr) if fill_attr is not None else inherited_fill
            stroke_col = _parse_svg_color(stroke_attr) if stroke_attr is not None else inherited_stroke
            sw_val = float(re.sub(r"[^0-9.]", "", sw_attr)) if sw_attr else inherited_sw

            if tag == "rect":
                x = float(node.attrib.get("x", 0))
                y = float(node.attrib.get("y", 0))
                w = float(node.attrib.get("width", 0))
                h = float(node.attrib.get("height", 0))
                rx = float(node.attrib.get("rx", 0))
                ry = float(node.attrib.get("ry", rx))
                grp.add(
                    RL_Rect(
                        x, y, w, h, rx=rx, ry=ry,
                        fillColor=fill_col if fill_attr != "none" else None,
                        strokeColor=stroke_col,
                        strokeWidth=sw_val if stroke_col else 0,
                    )
                )
            elif tag == "circle":
                cx = float(node.attrib.get("cx", 0))
                cy = float(node.attrib.get("cy", 0))
                r = float(node.attrib.get("r", 0))
                grp.add(
                    RL_Circle(
                        cx, cy, r,
                        fillColor=fill_col if fill_attr != "none" else None,
                        strokeColor=stroke_col,
                        strokeWidth=sw_val if stroke_col else 0,
                    )
                )
            elif tag == "ellipse":
                cx = float(node.attrib.get("cx", 0))
                cy = float(node.attrib.get("cy", 0))
                rx = float(node.attrib.get("rx", 0))
                ry = float(node.attrib.get("ry", 0))
                grp.add(
                    RL_Ellipse(
                        cx, cy, rx, ry,
                        fillColor=fill_col if fill_attr != "none" else None,
                        strokeColor=stroke_col,
                        strokeWidth=sw_val if stroke_col else 0,
                    )
                )
            elif tag == "line":
                x1 = float(node.attrib.get("x1", 0))
                y1 = float(node.attrib.get("y1", 0))
                x2 = float(node.attrib.get("x2", 0))
                y2 = float(node.attrib.get("y2", 0))
                grp.add(RL_Line(x1, y1, x2, y2, strokeColor=stroke_col or CMYKColor(0, 0, 0, 1), strokeWidth=sw_val))
            elif tag in ("polygon", "polyline"):
                pts_raw = [float(v) for v in re.split(r"[\s,]+", node.attrib.get("points", "").strip()) if v]
                if len(pts_raw) >= 4:
                    cls = RL_Polygon if tag == "polygon" else RL_PolyLine
                    kw = {"strokeColor": stroke_col, "strokeWidth": sw_val if stroke_col else 0}
                    if tag == "polygon":
                        kw["fillColor"] = fill_col if fill_attr != "none" else None
                    grp.add(cls(pts_raw, **kw))
            elif tag == "path":
                d_str = node.attrib.get("d", "")
                if d_str:
                    p = RL_Path(
                        fillColor=fill_col if fill_attr != "none" else None,
                        strokeColor=stroke_col,
                        strokeWidth=sw_val if stroke_col else 0,
                    )
                    _parse_svg_path_d(d_str, p)
                    grp.add(p)

            for child in node:
                walk(child, fill_col, stroke_col, sw_val)

        walk(root, CMYKColor(0, 0, 0, 0.9), None, 1.0)
        drawing.add(grp)
        return (drawing, vw, vh)
    except Exception:
        return None


class ResourceCache:
    """Cache de imagens e SVGs em memória para renderização rápida de 365+ páginas."""

    def __init__(self) -> None:
        self.images: dict[str, tuple[ImageReader, int, int]] = {}
        self.svgs: dict[str, tuple[RL_Drawing, float, float] | None] = {}

    def get_image(self, url: str) -> tuple[ImageReader, int, int] | None:
        if url in self.images:
            return self.images[url]
        path = _resolve_upload_path(url)
        if not path or path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
            return None
        try:
            with Image.open(path) as im:
                w_px, h_px = im.size
                # Converte para RGB/RGBA se necessário e mantém ImageReader em memória
                buf = io.BytesIO()
                fmt = "PNG" if im.mode in ("RGBA", "LA", "P") else "JPEG"
                if fmt == "JPEG" and im.mode != "RGB":
                    im = im.convert("RGB")
                im.save(buf, format=fmt, quality=95)
                buf.seek(0)
                reader = ImageReader(buf)
                self.images[url] = (reader, w_px, h_px)
                return self.images[url]
        except Exception:
            return None

    def get_svg(self, url: str) -> tuple[RL_Drawing, float, float] | None:
        if url in self.svgs:
            return self.svgs[url]
        path = _resolve_upload_path(url)
        if not path or path.suffix.lower() != ".svg":
            self.svgs[url] = None
            return None
        res = _build_svg_drawing(path)
        self.svgs[url] = res
        return res


def _wrap_text(c: canvas.Canvas, text: str, font_name: str, font_size: float, max_w_pt: float) -> list[str]:
    """Quebra texto em múltiplas linhas respeitando largura máxima em pontos."""
    lines: list[str] = []
    for paragraph in (text or "").splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for w in words:
            candidate = f"{current} {w}".strip() if current else w
            if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_w_pt:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)
    return lines or [""]


class AgendaPDFRenderer:
    """Renderizador de páginas da agenda em CMYK vetorial com precisão milimétrica."""

    def __init__(
        self,
        config: dict[str, Any],
        include_bleed: bool = True,
        include_crop_marks: bool = False,
        mirror_margins: bool = True,
        cache: ResourceCache | None = None,
    ) -> None:
        ensure_fonts_registered()
        self.config = config
        self.page_setup = dict(config.get("page_setup", {}))
        self.page_setup["mirror_margins"] = mirror_margins

        base_w = float(self.page_setup.get("width_mm", 150.0))
        base_h = float(self.page_setup.get("height_mm", 210.0))
        if self.page_setup.get("orientation", "portrait") == "landscape":
            self.trim_w_mm, self.trim_h_mm = max(base_w, base_h), min(base_w, base_h)
        else:
            self.trim_w_mm, self.trim_h_mm = min(base_w, base_h), max(base_w, base_h)

        self.bleed_mm = float(self.page_setup.get("bleed_mm", 3.0)) if include_bleed else 0.0
        self.include_crop_marks = include_crop_marks
        self.crop_pad_mm = 7.0 if include_crop_marks else 0.0

        self.media_w_mm = self.trim_w_mm + 2.0 * (self.bleed_mm + self.crop_pad_mm)
        self.media_h_mm = self.trim_h_mm + 2.0 * (self.bleed_mm + self.crop_pad_mm)
        self.origin_x = (self.bleed_mm + self.crop_pad_mm) * mm
        self.origin_y = (self.bleed_mm + self.crop_pad_mm) * mm

        self.colors = config.get("colors", {})
        self.ruling = config.get("ruling", {})
        self.footer = config.get("footer", {})
        self.cal_cfg = config.get("calendar", {})
        self.export_cfg = config.get("export", {})
        self.header_font = self.export_cfg.get("header_font_family", "Georgia")
        self.body_font = self.export_cfg.get("body_font_family", "Arial")
        self.cache = cache or ResourceCache()

    def px(self, x_mm: float) -> float:
        return self.origin_x + x_mm * mm

    def py(self, y_top_mm: float) -> float:
        return self.origin_y + (self.trim_h_mm - y_top_mm) * mm

    def draw_page(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        """Renderiza uma única página completa no canvas ReportLab."""
        c.setPageSize((self.media_w_mm * mm, self.media_h_mm * mm))

        # 1. Fundo (com sangria até a borda)
        bg = self.colors.get("background_color", {})
        if any(float(bg.get(ch, 0)) > 0 for ch in ("c", "m", "y", "k")):
            c.saveState()
            c.setFillColor(to_cmyk(bg))
            c.rect(
                self.origin_x - self.bleed_mm * mm,
                self.origin_y - self.bleed_mm * mm,
                (self.trim_w_mm + 2 * self.bleed_mm) * mm,
                (self.trim_h_mm + 2 * self.bleed_mm) * mm,
                fill=1,
                stroke=0,
            )
            c.restoreState()

        # 2. Conteúdo principal conforme page_type
        pt = page["page_type"]
        if pt == "special_cover":
            self._draw_special_cover(c, page)
        elif pt == "special_personal":
            self._draw_special_personal(c, page)
        elif pt == "special_calendar":
            self._draw_special_calendar(c, page)
        elif pt == "special_planner":
            self._draw_special_planner(c, page)
        elif pt == "special_goals":
            self._draw_special_goals(c, page)
        elif pt == "special_financial":
            self._draw_special_financial(c, page)
        elif pt == "special_birthdays":
            self._draw_special_birthdays(c, page)
        elif pt == "special_contacts":
            self._draw_special_contacts(c, page)
        elif pt == "special_notes":
            self._draw_special_notes(c, page)
        elif pt == "month_opener":
            self._draw_month_opener(c, page)
        elif pt == "daily_weekend_shared":
            self._draw_weekend_shared(c, page)
        elif pt == "daily_2dpp":
            self._draw_2dpp(c, page)
        elif pt == "weekly_spread":
            self._draw_weekly(c, page)
        elif pt == "monthly_view":
            self._draw_monthly_view(c, page)
        else:
            # daily_1dpp, financial_daily, corporate_daily, planner_daily
            self._draw_daily_single(c, page)

        # 3. Rodapé
        if page.get("show_footer"):
            self._draw_footer(c, page)

        # 4. Elementos visuais livres (Frases, Imagens, Formas)
        for el in page.get("active_elements", []):
            self._draw_element(c, el)

        # 5. Marcas de corte profissionais (quando solicitadas)
        if self.include_crop_marks:
            self._draw_crop_marks(c, page)

        c.showPage()

    def _draw_crop_marks(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        reg_black = CMYKColor(1.0, 1.0, 1.0, 1.0)
        c.setStrokeColor(reg_black)
        c.setFillColor(reg_black)
        c.setLineWidth(0.35)

        gap = max(self.bleed_mm + 1.0, 2.0) * mm
        mark_len = 5.0 * mm
        x0 = self.origin_x
        y0 = self.origin_y
        x1 = self.origin_x + self.trim_w_mm * mm
        y1 = self.origin_y + self.trim_h_mm * mm

        # 4 cantos (8 linhas de refilo exatas nos limites do formato final)
        corners = [
            (x0, y0, -1, -1),
            (x1, y0, 1, -1),
            (x0, y1, -1, 1),
            (x1, y1, 1, 1),
        ]
        for cx, cy, sx, sy in corners:
            c.line(cx + sx * gap, cy, cx + sx * (gap + mark_len), cy)
            c.line(cx, cy + sy * gap, cx, cy + sy * (gap + mark_len))

        # Slug discreto fora da área de sangria
        f_reg = resolve_font(self.body_font)
        c.setFont(f_reg, 5.5)
        c.drawString(
            x0,
            y0 - self.bleed_mm * mm - 4.2 * mm,
            f"Pág. {page['page_number']} | {self.trim_w_mm:.0f}x{self.trim_h_mm:.0f}mm | Sangria {self.bleed_mm:.1f}mm | CMYK",
        )
        c.restoreState()

    def _draw_ruling_area(
        self,
        c: canvas.Canvas,
        x_mm: float,
        y_top_mm: float,
        w_mm: float,
        h_mm: float,
        ruling_override: dict[str, Any] | None = None,
        show_times: bool | None = None,
        show_checks: bool | None = None,
        columns_override: int | None = None,
    ) -> None:
        r = ruling_override or self.ruling
        rtype = r.get("ruling_type", "horizontal")
        if rtype == "blank":
            return

        spacing = max(2.5, float(r.get("line_spacing_mm", 7.0)))
        thickness = max(0.1, float(r.get("line_thickness_pt", 0.5)))
        line_col = to_cmyk(r.get("line_color") or self.colors.get("ruling_line_color"))
        deco_col = to_cmyk(self.colors.get("decorative_color"))
        weekday_col = to_cmyk(self.colors.get("weekday_color"))

        use_times = self.ruling.get("show_time_column", False) if show_times is None else show_times
        use_checks = self.ruling.get("show_checkboxes", False) if show_checks is None else show_checks
        cols = columns_override or int(r.get("custom_columns", 1))

        c.saveState()
        c.setStrokeColor(line_col)
        c.setFillColor(line_col)
        c.setLineWidth(thickness)

        if rtype == "dotted":
            dot_r = max(0.25, thickness * 0.65)
            y = y_top_mm + spacing * 0.5
            while y <= y_top_mm + h_mm - 1.0:
                x = x_mm + 1.0
                while x <= x_mm + w_mm - 1.0:
                    c.circle(self.px(x), self.py(y), dot_r, fill=1, stroke=0)
                    x += spacing
                y += spacing
            c.restoreState()
            return

        if rtype == "grid":
            y = y_top_mm
            while y <= y_top_mm + h_mm + 0.05:
                c.line(self.px(x_mm), self.py(y), self.px(x_mm + w_mm), self.py(y))
                y += spacing
            x = x_mm
            while x <= x_mm + w_mm + 0.05:
                c.line(self.px(x), self.py(y_top_mm), self.px(x), self.py(y_top_mm + h_mm))
                x += spacing
            c.restoreState()
            return

        # Horizontal ou Custom
        count_mode = r.get("line_count_mode", "auto")
        max_possible = int(h_mm // spacing)
        if count_mode == "fixed":
            line_count = min(max_possible, int(r.get("fixed_line_count", 22)))
        else:
            line_count = max_possible

        col_w = w_mm / max(1, cols)
        col_gap = 3.0 if cols > 1 else 0.0
        inner_col_w = col_w - (col_gap * (cols - 1) / max(1, cols))

        # Preparar horários
        time_labels: list[str] = []
        if use_times:
            start_h = int(self.ruling.get("time_start_hour", 7))
            end_h = int(self.ruling.get("time_end_hour", 21))
            interval = int(self.ruling.get("time_interval_min", 60))
            cur_min = start_h * 60
            end_min = end_h * 60
            while cur_min <= end_min:
                time_labels.append(f"{cur_min // 60:02d}:{cur_min % 60:02d}")
                cur_min += interval

        f_time = resolve_font(self.body_font)

        for col_idx in range(cols):
            cx_mm = x_mm + col_idx * (inner_col_w + col_gap)
            for idx in range(1, line_count + 1):
                ly_mm = y_top_mm + idx * spacing
                if ly_mm > y_top_mm + h_mm + 0.1:
                    break
                c.setStrokeColor(line_col)
                c.setLineWidth(thickness)
                c.line(self.px(cx_mm), self.py(ly_mm), self.px(cx_mm + inner_col_w), self.py(ly_mm))

                # Horário na primeira coluna
                if col_idx == 0 and use_times and (idx - 1) < len(time_labels):
                    c.setFillColor(weekday_col)
                    c.setFont(f_time, 6.8)
                    c.drawString(self.px(cx_mm + 0.5), self.py(ly_mm - 1.3), time_labels[idx - 1])

                # Checkbox
                if use_checks:
                    cb_x = cx_mm + (11.0 if (col_idx == 0 and use_times) else 0.8)
                    cb_size = min(2.6, spacing * 0.45)
                    c.setStrokeColor(deco_col)
                    c.setLineWidth(0.45)
                    c.rect(self.px(cb_x), self.py(ly_mm - 0.8), cb_size * mm, cb_size * mm, fill=0, stroke=1)

        c.restoreState()

    def _draw_mini_calendar(
        self,
        c: canvas.Canvas,
        mini_cal: dict[str, Any],
        x_mm: float,
        y_top_mm: float,
        w_mm: float,
        h_mm: float,
        active_days: set[int] | None = None,
    ) -> None:
        c.saveState()
        title_col = to_cmyk(self.colors.get("title_color"))
        wd_col = to_cmyk(self.colors.get("weekday_color"))
        num_col = to_cmyk(self.colors.get("date_number_color"))
        hi_col = to_cmyk(self.colors.get("highlight_color"))
        deco_col = to_cmyk(self.colors.get("decorative_color"))

        f_bold = resolve_font(self.body_font, bold=True)
        f_reg = resolve_font(self.body_font)

        # Título do mini-calendário
        c.setFillColor(title_col)
        c.setFont(f_bold, 5.8)
        c.drawCentredString(self.px(x_mm + w_mm / 2), self.py(y_top_mm + 2.2), f"{mini_cal['month_name'].upper()} {mini_cal['year']}")

        c.setStrokeColor(deco_col)
        c.setLineWidth(0.35)
        c.line(self.px(x_mm), self.py(y_top_mm + 3.2), self.px(x_mm + w_mm), self.py(y_top_mm + 3.2))

        col_w = w_mm / 7.0
        weeks = mini_cal.get("weeks", [])
        row_count = len(weeks) + 1
        row_h = (h_mm - 3.8) / max(1, row_count)

        # Cabeçalhos D S T Q Q S S
        c.setFont(f_bold, 4.8)
        c.setFillColor(wd_col)
        for ci, hdr in enumerate(mini_cal.get("headers", [])):
            cx = x_mm + (ci + 0.5) * col_w
            c.drawCentredString(self.px(cx), self.py(y_top_mm + 3.5 + row_h * 0.72), hdr)

        c.setFont(f_reg, 4.8)
        for ri, wk in enumerate(weeks):
            ry = y_top_mm + 3.5 + (ri + 1) * row_h
            for ci, day_val in enumerate(wk):
                if day_val == 0:
                    continue
                cx = x_mm + (ci + 0.5) * col_w
                cy = ry + row_h * 0.72
                if active_days and day_val in active_days:
                    c.setFillColor(hi_col)
                    c.circle(self.px(cx), self.py(ry + row_h * 0.52), min(col_w, row_h) * 0.42 * mm, fill=1, stroke=0)
                    c.setFillColor(CMYKColor(0, 0, 0, 0))
                    c.setFont(f_bold, 4.8)
                else:
                    c.setFillColor(num_col)
                    c.setFont(f_reg, 4.8)
                c.drawCentredString(self.px(cx), self.py(cy), str(day_val))
        c.restoreState()

    def _draw_day_header(
        self,
        c: canvas.Canvas,
        entry: dict[str, Any],
        x_mm: float,
        y_top_mm: float,
        w_mm: float,
        header_h_mm: float,
        mini_cal: dict[str, Any] | None = None,
        compact: bool = False,
    ) -> None:
        c.saveState()
        title_col = to_cmyk(self.colors.get("title_color"))
        wd_col = to_cmyk(self.colors.get("weekday_color"))
        num_col = to_cmyk(self.colors.get("date_number_color"))
        deco_col = to_cmyk(self.colors.get("decorative_color"))
        wknd_col = to_cmyk(self.colors.get("weekend_color"))
        hol_col = to_cmyk(self.colors.get("holiday_color"))

        is_hol = entry.get("has_holiday", False)
        is_wknd = entry.get("is_weekend", False)
        active_num_col = hol_col if is_hol else (wknd_col if is_wknd else num_col)
        active_wd_col = hol_col if is_hol else (wknd_col if is_wknd else wd_col)

        f_num = resolve_font(self.header_font, bold=True)
        f_title = resolve_font(self.header_font, bold=True)
        f_body = resolve_font(self.body_font)
        f_body_bold = resolve_font(self.body_font, bold=True)

        # Caixa decorativa sutil atrás do número do dia
        box_size = 15.0 if compact else 20.0
        c.setFillColor(tint_cmyk(self.colors.get("holiday_color" if is_hol else ("weekend_color" if is_wknd else "decorative_color")), 0.14))
        c.roundRect(self.px(x_mm), self.py(y_top_mm + box_size), box_size * mm, box_size * mm, 2.2 * mm, fill=1, stroke=0)

        # Número do dia
        c.setFillColor(active_num_col)
        c.setFont(f_num, 22 if compact else 28)
        c.drawCentredString(self.px(x_mm + box_size / 2), self.py(y_top_mm + box_size * 0.72), f"{entry['day']:02d}")

        # Mês + Ano + Dia da semana
        info_x = x_mm + box_size + 4.0
        c.setFillColor(title_col)
        c.setFont(f_title, 10.5 if compact else 13.0)
        year_str = f" {entry['year']}" if entry.get("year") else ""
        c.drawString(self.px(info_x), self.py(y_top_mm + 5.8), f"{entry['month_label']}{year_str}")

        c.setFillColor(active_wd_col)
        c.setFont(f_body_bold, 8.5 if compact else 10.0)
        c.drawString(self.px(info_x), self.py(y_top_mm + (10.5 if compact else 11.8)), entry["weekday_name"])

        # Contagem de dias ou círculo permanente
        c.setFillColor(wd_col)
        c.setFont(f_body, 6.8)
        if entry.get("is_dated"):
            c.drawString(self.px(info_x), self.py(y_top_mm + (14.5 if compact else 16.5)), f"Dia {entry['day_of_year']} • Faltam {entry['days_remaining']}")
        else:
            c.drawString(self.px(info_x), self.py(y_top_mm + (14.5 if compact else 16.5)), "Marque:  (D)  (S)  (T)  (Q)  (Q)  (S)  (S)")

        # Badge de Feriado / Data Comemorativa
        if is_hol:
            hol_text = " • ".join(h["name"] for h in entry["holidays"])
            badge_y = y_top_mm + (16.5 if compact else 19.5)
            c.setFillColor(tint_cmyk(self.colors.get("holiday_color"), 0.14))
            badge_w = min(w_mm - (38.0 if mini_cal else 4.0), max(38.0, len(hol_text) * 1.45 + 6.0))
            c.roundRect(self.px(x_mm), self.py(badge_y + 4.8), badge_w * mm, 4.8 * mm, 1.2 * mm, fill=1, stroke=0)
            c.setFillColor(hol_col)
            c.setFont(f_body_bold, 6.8)
            c.drawString(self.px(x_mm + 2.0), self.py(badge_y + 3.5), hol_text[:72])

        # Mini-calendário
        if mini_cal and not compact:
            mc_w = 34.0
            mc_h = min(23.0, header_h_mm - 2.0)
            self._draw_mini_calendar(c, mini_cal, x_mm + w_mm - mc_w, y_top_mm, mc_w, mc_h, active_days={entry["day"]})

        # Linha divisória
        c.setStrokeColor(deco_col)
        c.setLineWidth(0.75)
        c.line(self.px(x_mm), self.py(y_top_mm + header_h_mm - 1.5), self.px(x_mm + w_mm), self.py(y_top_mm + header_h_mm - 1.5))
        c.restoreState()

    def _draw_daily_single(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        m = page["effective_margins"]
        x0 = m["left"]
        w = self.trim_w_mm - m["left"] - m["right"]
        y0 = m["top"]
        header_h = max(22.0, float(self.ruling.get("margin_top_offset_mm", 28.0)))

        entry = page["dates"][0]
        self._draw_day_header(c, entry, x0, y0, w, header_h, page.get("mini_calendar"))

        r_left = x0 + float(self.ruling.get("margin_left_offset_mm", 0.0))
        r_right_off = float(self.ruling.get("margin_right_offset_mm", 0.0))
        r_w = max(20.0, w - float(self.ruling.get("margin_left_offset_mm", 0.0)) - r_right_off)
        r_top = y0 + header_h + 1.5
        r_bot = self.trim_h_mm - m["bottom"] - float(self.ruling.get("margin_bottom_offset_mm", 14.0))
        r_h = max(20.0, r_bot - r_top)

        pt = page["page_type"]
        if pt == "financial_daily":
            self._draw_financial_daily_body(c, r_left, r_top, r_w, r_h)
        elif pt == "corporate_daily":
            self._draw_corporate_daily_body(c, r_left, r_top, r_w, r_h)
        elif pt == "planner_daily":
            self._draw_planner_daily_body(c, r_left, r_top, r_w, r_h)
        else:
            self._draw_ruling_area(c, r_left, r_top, r_w, r_h)

    def _draw_financial_daily_body(self, c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
        c.saveState()
        deco = to_cmyk(self.colors.get("decorative_color"))
        title_col = to_cmyk(self.colors.get("title_color"))
        line_col = to_cmyk(self.colors.get("ruling_line_color"))
        f_b = resolve_font(self.body_font, bold=True)

        # Topo: Pauta de Compromissos (45% da altura)
        top_h = h * 0.44
        c.setFillColor(title_col)
        c.setFont(f_b, 7.2)
        c.drawString(self.px(x), self.py(y + 3.0), "COMPROMISSOS & TAREFAS")
        self._draw_ruling_area(c, x, y + 4.5, w, top_h - 5.0)

        # Base: Fluxo de Caixa Diário (Entradas / Saídas)
        fin_y = y + top_h + 2.0
        fin_h = h - top_h - 2.0
        c.setFillColor(tint_cmyk(self.colors.get("decorative_color"), 0.18))
        c.rect(self.px(x), self.py(fin_y + 5.5), w * mm, 5.5 * mm, fill=1, stroke=0)
        c.setFillColor(title_col)
        c.setFont(f_b, 7.0)
        c.drawString(self.px(x + 2.0), self.py(fin_y + 3.9), "DESCRIÇÃO / MOVIMENTAÇÃO FINANCEIRA")
        c.drawRightString(self.px(x + w * 0.78), self.py(fin_y + 3.9), "ENTRADA (R$)")
        c.drawRightString(self.px(x + w - 2.0), self.py(fin_y + 3.9), "SAÍDA (R$)")

        row_sp = float(self.ruling.get("line_spacing_mm", 7.0))
        cur_y = fin_y + 5.5 + row_sp
        while cur_y <= fin_y + fin_h - 8.0:
            c.setStrokeColor(line_col)
            c.setLineWidth(0.45)
            c.line(self.px(x), self.py(cur_y), self.px(x + w), self.py(cur_y))
            cur_y += row_sp

        # Colunas verticais
        c.setStrokeColor(deco)
        c.setLineWidth(0.5)
        c.line(self.px(x + w * 0.60), self.py(fin_y), self.px(x + w * 0.60), self.py(fin_y + fin_h - 8.0))
        c.line(self.px(x + w * 0.80), self.py(fin_y), self.px(x + w * 0.80), self.py(fin_y + fin_h - 8.0))

        # Barra de saldo do dia
        sum_y = fin_y + fin_h - 7.0
        c.setFillColor(tint_cmyk(self.colors.get("highlight_color"), 0.15))
        c.roundRect(self.px(x), self.py(sum_y + 6.5), w * mm, 6.5 * mm, 1.5 * mm, fill=1, stroke=0)
        c.setFillColor(title_col)
        c.setFont(f_b, 7.2)
        c.drawString(self.px(x + 2.5), self.py(sum_y + 4.3), "SALDO ANTERIOR: R$ ________     ENTRADAS: R$ ________     SAÍDAS: R$ ________     SALDO: R$ ________")
        c.restoreState()

    def _draw_corporate_daily_body(self, c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
        c.saveState()
        title_col = to_cmyk(self.colors.get("title_color"))
        deco = to_cmyk(self.colors.get("decorative_color"))
        f_b = resolve_font(self.body_font, bold=True)

        # Bloco superior: Prioridades Executivas (22 mm)
        prio_h = 24.0
        c.setStrokeColor(deco)
        c.setLineWidth(0.6)
        c.roundRect(self.px(x), self.py(y + prio_h), w * mm, prio_h * mm, 2.0 * mm, fill=0, stroke=1)
        c.setFillColor(title_col)
        c.setFont(f_b, 7.0)
        c.drawString(self.px(x + 2.5), self.py(y + 4.0), "PRIORIDADES DO DIA / TOP 3")
        self._draw_ruling_area(c, x + 2.0, y + 5.5, w - 4.0, prio_h - 6.5, show_times=False, show_checks=True)

        # Coluna esquerda: Horários / Reuniões; Coluna direita: Pendências & Follow-up
        body_y = y + prio_h + 3.0
        body_h = h - prio_h - 3.0
        left_w = w * 0.62
        right_w = w - left_w - 4.0

        c.setFillColor(title_col)
        c.setFont(f_b, 7.0)
        c.drawString(self.px(x), self.py(body_y + 3.0), "AGENDA DE HORÁRIOS & REUNIÕES")
        self._draw_ruling_area(c, x, body_y + 4.5, left_w, body_h - 5.0, show_times=True, show_checks=False)

        c.setFillColor(title_col)
        c.drawString(self.px(x + left_w + 4.0), self.py(body_y + 3.0), "DELEGAR / FOLLOW-UP")
        self._draw_ruling_area(c, x + left_w + 4.0, body_y + 4.5, right_w, body_h - 5.0, show_times=False, show_checks=True)
        c.restoreState()

    def _draw_planner_daily_body(self, c: canvas.Canvas, x: float, y: float, w: float, h: float) -> None:
        c.saveState()
        title_col = to_cmyk(self.colors.get("title_color"))
        deco = to_cmyk(self.colors.get("decorative_color"))
        f_b = resolve_font(self.body_font, bold=True)

        left_w = w * 0.56
        right_w = w - left_w - 4.0

        c.setFillColor(title_col)
        c.setFont(f_b, 7.2)
        c.drawString(self.px(x), self.py(y + 3.0), "CRONOGRAMA DO DIA")
        self._draw_ruling_area(c, x, y + 4.5, left_w, h - 5.0, show_times=True, show_checks=False)

        rx = x + left_w + 4.0
        box1_h = h * 0.45
        c.setStrokeColor(deco)
        c.setLineWidth(0.55)
        c.roundRect(self.px(rx), self.py(y + box1_h), right_w * mm, box1_h * mm, 2.0 * mm, fill=0, stroke=1)
        c.setFillColor(title_col)
        c.drawString(self.px(rx + 2.0), self.py(y + 3.8), "TAREFAS & CHECKLIST")
        self._draw_ruling_area(c, rx + 1.5, y + 5.0, right_w - 3.0, box1_h - 6.0, show_times=False, show_checks=True)

        box2_y = y + box1_h + 3.0
        box2_h = h - box1_h - 3.0
        c.setStrokeColor(deco)
        c.roundRect(self.px(rx), self.py(box2_y + box2_h), right_w * mm, box2_h * mm, 2.0 * mm, fill=0, stroke=1)
        c.setFillColor(title_col)
        c.drawString(self.px(rx + 2.0), self.py(box2_y + 3.8), "NOTAS & GRATIDÃO")
        self._draw_ruling_area(c, rx + 1.5, box2_y + 5.0, right_w - 3.0, box2_h - 6.0, show_times=False, show_checks=False)
        c.restoreState()

    def _draw_weekend_shared(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        m = page["effective_margins"]
        x0 = m["left"]
        w = self.trim_w_mm - m["left"] - m["right"]
        y0 = m["top"]
        usable_h = self.trim_h_mm - m["top"] - m["bottom"] - float(self.ruling.get("margin_bottom_offset_mm", 14.0))
        half_h = (usable_h - 5.0) / 2.0

        for idx, entry in enumerate(page["dates"][:2]):
            by = y0 + idx * (half_h + 5.0)
            hdr_h = 20.0
            mc = page.get("mini_calendar") if idx == 0 else None
            self._draw_day_header(c, entry, x0, by, w, hdr_h, mc, compact=True)
            r_left = x0 + float(self.ruling.get("margin_left_offset_mm", 0.0))
            r_w = max(20.0, w - float(self.ruling.get("margin_left_offset_mm", 0.0)) - float(self.ruling.get("margin_right_offset_mm", 0.0)))
            self._draw_ruling_area(c, r_left, by + hdr_h + 1.0, r_w, max(12.0, half_h - hdr_h - 1.5), show_times=False)

    def _draw_2dpp(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        m = page["effective_margins"]
        x0 = m["left"]
        w = self.trim_w_mm - m["left"] - m["right"]
        y0 = m["top"]
        usable_h = self.trim_h_mm - m["top"] - m["bottom"] - float(self.ruling.get("margin_bottom_offset_mm", 14.0))
        half_h = (usable_h - 5.0) / 2.0

        for idx, entry in enumerate(page["dates"][:2]):
            by = y0 + idx * (half_h + 5.0)
            hdr_h = 20.0
            mc = page.get("mini_calendar") if idx == 0 else None
            self._draw_day_header(c, entry, x0, by, w, hdr_h, mc, compact=True)
            r_left = x0 + float(self.ruling.get("margin_left_offset_mm", 0.0))
            r_w = max(20.0, w - float(self.ruling.get("margin_left_offset_mm", 0.0)) - float(self.ruling.get("margin_right_offset_mm", 0.0)))
            self._draw_ruling_area(c, r_left, by + hdr_h + 1.0, r_w, max(12.0, half_h - hdr_h - 1.5))

    def _draw_weekly(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        m = page["effective_margins"]
        x0 = m["left"]
        w = self.trim_w_mm - m["left"] - m["right"]
        y0 = m["top"]
        usable_h = self.trim_h_mm - m["top"] - m["bottom"] - float(self.ruling.get("margin_bottom_offset_mm", 14.0))

        title_col = to_cmyk(self.colors.get("title_color"))
        deco = to_cmyk(self.colors.get("decorative_color"))
        wknd_col = to_cmyk(self.colors.get("weekend_color"))
        hol_col = to_cmyk(self.colors.get("holiday_color"))
        f_title = resolve_font(self.header_font, bold=True)
        f_b = resolve_font(self.body_font, bold=True)

        c.setFillColor(title_col)
        c.setFont(f_title, 11.5)
        c.drawString(self.px(x0), self.py(y0 + 5.0), page["title"])
        c.setStrokeColor(deco)
        c.setLineWidth(0.7)
        c.line(self.px(x0), self.py(y0 + 7.5), self.px(x0 + w), self.py(y0 + 7.5))

        grid_y = y0 + 10.0
        grid_h = usable_h - 10.0
        cols, rows = 2, 4
        gap = 3.5
        cell_w = (w - gap) / cols
        cell_h = (grid_h - gap * (rows - 1)) / rows

        dates = page.get("dates", [])
        for slot in range(8):
            r_idx = slot // cols
            c_idx = slot % cols
            sx = x0 + c_idx * (cell_w + gap)
            sy = grid_y + r_idx * (cell_h + gap)

            c.setStrokeColor(deco)
            c.setLineWidth(0.5)
            c.roundRect(self.px(sx), self.py(sy + cell_h), cell_w * mm, cell_h * mm, 1.8 * mm, fill=0, stroke=1)

            if slot < len(dates):
                d = dates[slot]
                is_h = d.get("has_holiday")
                col = hol_col if is_h else (wknd_col if d.get("is_weekend") else title_col)
                c.setFillColor(tint_cmyk(self.colors.get("holiday_color" if is_h else "decorative_color"), 0.14))
                c.rect(self.px(sx), self.py(sy + 5.8), cell_w * mm, 5.8 * mm, fill=1, stroke=0)
                c.setFillColor(col)
                c.setFont(f_b, 8.0)
                c.drawString(self.px(sx + 2.0), self.py(sy + 4.1), f"{d['day']:02d}/{d['month']:02d} • {d['weekday_name']}")
                self._draw_ruling_area(c, sx + 1.5, sy + 6.2, cell_w - 3.0, cell_h - 7.0, show_times=False)
            elif slot == 7 or not dates:
                c.setFillColor(tint_cmyk(self.colors.get("highlight_color"), 0.14))
                c.rect(self.px(sx), self.py(sy + 5.8), cell_w * mm, 5.8 * mm, fill=1, stroke=0)
                c.setFillColor(title_col)
                c.setFont(f_b, 8.0)
                label = "NOTAS & METAS DA SEMANA" if (slot == 7 or dates) else f"DIA {slot + 1} (D S T Q Q S S)"
                c.drawString(self.px(sx + 2.0), self.py(sy + 4.1), label)
                self._draw_ruling_area(c, sx + 1.5, sy + 6.2, cell_w - 3.0, cell_h - 7.0, show_times=False)
        c.restoreState()

    def _draw_monthly_view(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        m = page["effective_margins"]
        x0 = m["left"]
        w = self.trim_w_mm - m["left"] - m["right"]
        y0 = m["top"]
        usable_h = self.trim_h_mm - m["top"] - m["bottom"] - float(self.ruling.get("margin_bottom_offset_mm", 14.0))

        title_col = to_cmyk(self.colors.get("title_color"))
        deco = to_cmyk(self.colors.get("decorative_color"))
        num_col = to_cmyk(self.colors.get("date_number_color"))
        hol_col = to_cmyk(self.colors.get("holiday_color"))
        f_title = resolve_font(self.header_font, bold=True)
        f_b = resolve_font(self.body_font, bold=True)
        f_r = resolve_font(self.body_font)

        c.setFillColor(title_col)
        c.setFont(f_title, 13.0)
        c.drawString(self.px(x0), self.py(y0 + 5.5), page["title"])

        mini = page.get("mini_calendar") or {}
        weeks = mini.get("weeks", [])
        headers = mini.get("headers", ["D", "S", "T", "Q", "Q", "S", "S"])
        hol_by_day = {d["day"]: d["holidays"][0]["name"] for d in page.get("dates", []) if d.get("has_holiday")}

        grid_y = y0 + 10.0
        grid_h = usable_h * 0.72
        col_w = w / 7.0
        row_h = (grid_h - 6.0) / max(1, len(weeks))

        # Cabeçalho semana
        c.setFillColor(tint_cmyk(self.colors.get("decorative_color"), 0.22))
        c.rect(self.px(x0), self.py(grid_y + 6.0), w * mm, 6.0 * mm, fill=1, stroke=0)
        c.setFillColor(title_col)
        c.setFont(f_b, 7.5)
        for ci, h_lbl in enumerate(headers):
            c.drawCentredString(self.px(x0 + (ci + 0.5) * col_w), self.py(grid_y + 4.3), h_lbl)

        for ri, wk in enumerate(weeks):
            ry = grid_y + 6.0 + ri * row_h
            for ci, day_num in enumerate(wk):
                cx = x0 + ci * col_w
                c.setStrokeColor(deco)
                c.setLineWidth(0.4)
                c.rect(self.px(cx), self.py(ry + row_h), col_w * mm, row_h * mm, fill=0, stroke=1)
                if day_num > 0:
                    is_h = day_num in hol_by_day
                    c.setFillColor(hol_col if is_h else num_col)
                    c.setFont(f_b, 7.5)
                    c.drawString(self.px(cx + 1.5), self.py(ry + 3.8), str(day_num))
                    if is_h:
                        c.setFont(f_r, 4.8)
                        c.drawString(self.px(cx + 1.5), self.py(ry + 7.2), hol_by_day[day_num][:14])

        # Área inferior: Objetivos do mês
        obj_y = grid_y + grid_h + 4.0
        obj_h = usable_h - grid_h - 14.0
        if obj_h > 16.0:
            c.setFillColor(title_col)
            c.setFont(f_b, 8.0)
            c.drawString(self.px(x0), self.py(obj_y + 3.5), "OBJETIVOS & PRIORIDADES DO MÊS")
            self._draw_ruling_area(c, x0, obj_y + 5.0, w, obj_h - 5.0, show_times=False, show_checks=True)
        c.restoreState()

    def _draw_month_opener(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        m = page["effective_margins"]
        x0 = m["left"]
        w = self.trim_w_mm - m["left"] - m["right"]
        y0 = m["top"]
        h = self.trim_h_mm - m["top"] - m["bottom"] - 10.0

        title_col = to_cmyk(self.colors.get("title_color"))
        deco = to_cmyk(self.colors.get("decorative_color"))
        hi = to_cmyk(self.colors.get("highlight_color"))
        f_title = resolve_font(self.header_font, bold=True)
        f_sub = resolve_font(self.header_font, italic=True)
        f_b = resolve_font(self.body_font, bold=True)

        # Moldura editorial
        c.setStrokeColor(deco)
        c.setLineWidth(1.0)
        c.roundRect(self.px(x0), self.py(y0 + h), w * mm, h * mm, 4.0 * mm, fill=0, stroke=1)

        # Faixa superior decorativa
        c.setFillColor(tint_cmyk(self.colors.get("decorative_color"), 0.16))
        c.roundRect(self.px(x0 + 4.0), self.py(y0 + 36.0), (w - 8.0) * mm, 30.0 * mm, 3.0 * mm, fill=1, stroke=0)

        month_num = page.get("month") or 1
        c.setFillColor(hi)
        c.setFont(f_title, 10.0)
        c.drawCentredString(self.px(x0 + w / 2), self.py(y0 + 13.5), f"MÊS {month_num:02d}" + (f" • {page['year']}" if page.get("year") else ""))

        c.setFillColor(title_col)
        c.setFont(f_title, 24.0)
        c.drawCentredString(self.px(x0 + w / 2), self.py(y0 + 25.0), page["title"])

        c.setFillColor(to_cmyk(self.colors.get("weekday_color")))
        c.setFont(f_sub, 9.0)
        c.drawCentredString(self.px(x0 + w / 2), self.py(y0 + 32.0), "Planejamento, Metas & Datas Importantes")

        # Mini calendário centralizado
        cur_y = y0 + 42.0
        if page.get("mini_calendar"):
            mc_w = min(w - 16.0, 74.0)
            mc_h = 46.0
            self._draw_mini_calendar(c, page["mini_calendar"], x0 + (w - mc_w) / 2, cur_y, mc_w, mc_h)
            cur_y += mc_h + 6.0

        # Blocos de Metas do Mês e Notas
        rem_h = max(30.0, y0 + h - cur_y - 6.0)
        c.setFillColor(title_col)
        c.setFont(f_b, 8.5)
        c.drawString(self.px(x0 + 6.0), self.py(cur_y + 3.0), "METAS & FOCO DO MÊS")
        self._draw_ruling_area(c, x0 + 6.0, cur_y + 5.0, w - 12.0, rem_h - 6.0, show_times=False, show_checks=True)
        c.restoreState()

    def _draw_special_cover(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        m = page["effective_margins"]
        x0 = m["left"]
        w = self.trim_w_mm - m["left"] - m["right"]
        y0 = m["top"]
        h = self.trim_h_mm - m["top"] - m["bottom"]

        title_col = to_cmyk(self.colors.get("title_color"))
        deco = to_cmyk(self.colors.get("decorative_color"))
        wd_col = to_cmyk(self.colors.get("weekday_color"))
        f_title = resolve_font(self.header_font, bold=True)
        f_sub = resolve_font(self.header_font, italic=True)
        f_b = resolve_font(self.body_font, bold=True)

        c.setStrokeColor(deco)
        c.setLineWidth(1.2)
        c.roundRect(self.px(x0 + 4), self.py(y0 + h - 4), (w - 8) * mm, (h - 8) * mm, 4 * mm, fill=0, stroke=1)
        c.setLineWidth(0.4)
        c.roundRect(self.px(x0 + 6.5), self.py(y0 + h - 6.5), (w - 13) * mm, (h - 13) * mm, 3 * mm, fill=0, stroke=1)

        cx = x0 + w / 2
        c.setFillColor(title_col)
        c.setFont(f_title, 26.0)
        c.drawCentredString(self.px(cx), self.py(y0 + h * 0.38), str(page.get("title", "AGENDA")))

        c.setFillColor(wd_col)
        c.setFont(f_sub, 11.0)
        c.drawCentredString(self.px(cx), self.py(y0 + h * 0.45), str(page.get("subtitle", "")))

        recipient = page.get("recipient") or {}
        owner_name = recipient.get("nome") or self.footer.get("professional_name") or ""
        company_name = recipient.get("empresa") or self.footer.get("company_name") or ""
        if owner_name or company_name:
            c.setFillColor(tint_cmyk(self.colors.get("decorative_color"), 0.16))
            c.roundRect(self.px(cx - 45), self.py(y0 + h * 0.72), 90 * mm, 22 * mm, 2.5 * mm, fill=1, stroke=0)
            c.setFillColor(title_col)
            c.setFont(f_b, 10.5)
            if owner_name:
                c.drawCentredString(self.px(cx), self.py(y0 + h * 0.64), owner_name)
            if company_name:
                c.setFont(resolve_font(self.body_font), 8.5)
                c.drawCentredString(self.px(cx), self.py(y0 + h * 0.69), company_name)
        c.restoreState()

    def _draw_special_header(self, c: canvas.Canvas, page: dict[str, Any]) -> tuple[float, float, float, float]:
        m = page["effective_margins"]
        x0 = m["left"]
        w = self.trim_w_mm - m["left"] - m["right"]
        y0 = m["top"]
        h = self.trim_h_mm - m["top"] - m["bottom"] - 12.0

        title_col = to_cmyk(self.colors.get("title_color"))
        deco = to_cmyk(self.colors.get("decorative_color"))
        f_t = resolve_font(self.header_font, bold=True)

        c.setFillColor(title_col)
        c.setFont(f_t, 13.0)
        c.drawString(self.px(x0), self.py(y0 + 6.0), page.get("title", ""))
        c.setStrokeColor(deco)
        c.setLineWidth(0.8)
        c.line(self.px(x0), self.py(y0 + 9.0), self.px(x0 + w), self.py(y0 + 9.0))
        return (x0, y0 + 13.0, w, h - 13.0)

    def _draw_special_personal(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        x0, y0, w, h = self._draw_special_header(c, page)
        fields = [
            "Nome Completo",
            "Empresa / Profissão",
            "Endereço",
            "Cidade / UF / CEP",
            "Telefone / WhatsApp",
            "E-mail",
            "Site / Redes Sociais",
            "Em caso de emergência avisar",
            "Telefone de emergência",
            "Tipo Sanguíneo / Alergias / Plano de Saúde",
        ]
        f_b = resolve_font(self.body_font, bold=True)
        lbl_col = to_cmyk(self.colors.get("weekday_color"))
        line_col = to_cmyk(self.colors.get("ruling_line_color"))
        step = min(13.5, h / max(1, len(fields)))

        recipient = page.get("recipient") or {}
        for i, label in enumerate(fields):
            fy = y0 + i * step
            c.setFillColor(lbl_col)
            c.setFont(f_b, 7.5)
            c.drawString(self.px(x0), self.py(fy + 3.5), label.upper())
            if i == 0 and recipient.get("nome"):
                c.setFillColor(to_cmyk(self.colors.get("title_color")))
                c.drawString(self.px(x0 + 2.0), self.py(fy + 8.5), recipient["nome"])
            if i == 1 and recipient.get("empresa"):
                c.setFillColor(to_cmyk(self.colors.get("title_color")))
                c.drawString(self.px(x0 + 2.0), self.py(fy + 8.5), recipient["empresa"])
            c.setStrokeColor(line_col)
            c.setLineWidth(0.5)
            c.line(self.px(x0), self.py(fy + 10.0), self.px(x0 + w), self.py(fy + 10.0))
        c.restoreState()

    def _draw_special_calendar(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        x0, y0, w, h = self._draw_special_header(c, page)
        extra = page.get("extra", {})
        cals = extra.get("calendars_current", [])
        cols, rows = 3, 4
        gap_x, gap_y = 4.0, 4.0
        cw = (w - gap_x * (cols - 1)) / cols
        ch = (h - gap_y * (rows - 1)) / rows
        for idx, mc in enumerate(cals[:12]):
            r_i = idx // cols
            c_i = idx % cols
            self._draw_mini_calendar(c, mc, x0 + c_i * (cw + gap_x), y0 + r_i * (ch + gap_y), cw, ch)
        c.restoreState()

    def _draw_special_planner(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        x0, y0, w, h = self._draw_special_header(c, page)
        deco = to_cmyk(self.colors.get("decorative_color"))
        title_col = to_cmyk(self.colors.get("title_color"))
        f_b = resolve_font(self.body_font, bold=True)
        cols, rows = 3, 4
        gap = 3.5
        cw = (w - gap * (cols - 1)) / cols
        ch = (h - gap * (rows - 1)) / rows
        for idx in range(12):
            r_i = idx // cols
            c_i = idx % cols
            bx = x0 + c_i * (cw + gap)
            by = y0 + r_i * (ch + gap)
            c.setStrokeColor(deco)
            c.setLineWidth(0.5)
            c.roundRect(self.px(bx), self.py(by + ch), cw * mm, ch * mm, 1.5 * mm, fill=0, stroke=1)
            c.setFillColor(tint_cmyk(self.colors.get("decorative_color"), 0.16))
            c.rect(self.px(bx), self.py(by + 5.0), cw * mm, 5.0 * mm, fill=1, stroke=0)
            c.setFillColor(title_col)
            c.setFont(f_b, 7.2)
            c.drawString(self.px(bx + 2.0), self.py(by + 3.6), MONTH_NAMES_PT[idx + 1].upper())
            self._draw_ruling_area(c, bx + 1.5, by + 5.5, cw - 3.0, ch - 6.5, show_times=False, show_checks=False)
        c.restoreState()

    def _draw_special_goals(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        x0, y0, w, h = self._draw_special_header(c, page)
        deco = to_cmyk(self.colors.get("decorative_color"))
        title_col = to_cmyk(self.colors.get("title_color"))
        f_b = resolve_font(self.body_font, bold=True)
        sections = [
            "METAS PROFISSIONAIS & CARREIRA",
            "METAS PESSOAIS & FAMÍLIA",
            "SAÚDE, BEM-ESTAR & HÁBITOS",
            "PROJETOS, ESTUDOS & FINANÇAS",
        ]
        cols, rows = 2, 2
        gap = 4.5
        cw = (w - gap) / 2.0
        ch = (h - gap) / 2.0
        for idx, sec in enumerate(sections):
            r_i = idx // cols
            c_i = idx % cols
            bx = x0 + c_i * (cw + gap)
            by = y0 + r_i * (ch + gap)
            c.setStrokeColor(deco)
            c.setLineWidth(0.6)
            c.roundRect(self.px(bx), self.py(by + ch), cw * mm, ch * mm, 2.0 * mm, fill=0, stroke=1)
            c.setFillColor(title_col)
            c.setFont(f_b, 7.5)
            c.drawString(self.px(bx + 2.5), self.py(by + 4.5), sec)
            self._draw_ruling_area(c, bx + 2.0, by + 6.5, cw - 4.0, ch - 8.0, show_times=False, show_checks=True)
        c.restoreState()

    def _draw_special_financial(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        x0, y0, w, h = self._draw_special_header(c, page)
        deco = to_cmyk(self.colors.get("decorative_color"))
        title_col = to_cmyk(self.colors.get("title_color"))
        f_b = resolve_font(self.body_font, bold=True)
        f_r = resolve_font(self.body_font)
        rows = 14  # Cabeçalho + 12 meses + Total
        rh = h / rows
        c.setFillColor(tint_cmyk(self.colors.get("decorative_color"), 0.2))
        c.rect(self.px(x0), self.py(y0 + rh), w * mm, rh * mm, fill=1, stroke=0)
        c.setFillColor(title_col)
        c.setFont(f_b, 7.5)
        c.drawString(self.px(x0 + 2.0), self.py(y0 + rh * 0.68), "MÊS")
        c.drawRightString(self.px(x0 + w * 0.50), self.py(y0 + rh * 0.68), "ENTRADAS (R$)")
        c.drawRightString(self.px(x0 + w * 0.75), self.py(y0 + rh * 0.68), "SAÍDAS (R$)")
        c.drawRightString(self.px(x0 + w - 2.0), self.py(y0 + rh * 0.68), "SALDO (R$)")

        for idx in range(1, 14):
            ry = y0 + idx * rh
            c.setStrokeColor(deco)
            c.setLineWidth(0.45)
            c.rect(self.px(x0), self.py(ry + rh), w * mm, rh * mm, fill=0, stroke=1)
            c.setFillColor(title_col)
            c.setFont(f_b if idx == 13 else f_r, 7.8)
            lbl = "TOTAL ANUAL" if idx == 13 else MONTH_NAMES_PT[idx].upper()
            c.drawString(self.px(x0 + 2.0), self.py(ry + rh * 0.68), lbl)
        c.restoreState()

    def _draw_special_birthdays(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        self._draw_special_planner(c, page)

    def _draw_special_contacts(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        x0, y0, w, h = self._draw_special_header(c, page)
        deco = to_cmyk(self.colors.get("decorative_color"))
        title_col = to_cmyk(self.colors.get("title_color"))
        f_b = resolve_font(self.body_font, bold=True)
        c.setFillColor(tint_cmyk(self.colors.get("decorative_color"), 0.18))
        c.rect(self.px(x0), self.py(y0 + 6.0), w * mm, 6.0 * mm, fill=1, stroke=0)
        c.setFillColor(title_col)
        c.setFont(f_b, 7.2)
        c.drawString(self.px(x0 + 2.0), self.py(y0 + 4.2), "NOME / EMPRESA")
        c.drawString(self.px(x0 + w * 0.44), self.py(y0 + 4.2), "TELEFONE / WHATSAPP")
        c.drawString(self.px(x0 + w * 0.72), self.py(y0 + 4.2), "E-MAIL")
        self._draw_ruling_area(c, x0, y0 + 6.5, w, h - 7.0, show_times=False, show_checks=False)
        c.setStrokeColor(deco)
        c.setLineWidth(0.4)
        c.line(self.px(x0 + w * 0.42), self.py(y0), self.px(x0 + w * 0.42), self.py(y0 + h))
        c.line(self.px(x0 + w * 0.70), self.py(y0), self.px(x0 + w * 0.70), self.py(y0 + h))
        c.restoreState()

    def _draw_special_notes(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        x0, y0, w, h = self._draw_special_header(c, page)
        self._draw_ruling_area(c, x0, y0, w, h, show_times=False, show_checks=False)
        c.restoreState()

    def _draw_footer(self, c: canvas.Canvas, page: dict[str, Any]) -> None:
        c.saveState()
        m = page["effective_margins"]
        x0 = m["left"]
        w = self.trim_w_mm - m["left"] - m["right"]
        dist = float(self.footer.get("distance_from_bottom_mm", 8.0))
        fy_top = self.trim_h_mm - dist

        recipient = page.get("recipient") or {}
        company = recipient.get("empresa") or self.footer.get("company_name") or ""
        prof = recipient.get("nome") or self.footer.get("professional_name") or ""
        extra = recipient.get("extra") or self.footer.get("extra_text") or ""

        parts = [p.strip() for p in (company, prof, extra) if p and p.strip()]
        footer_text = "  •  ".join(parts)

        text_col = to_cmyk(self.footer.get("text_color"))
        font_name = resolve_font(
            self.footer.get("font_family", "Arial"),
            bold=bool(self.footer.get("bold", False)),
            italic=bool(self.footer.get("italic", False)),
        )
        font_size = float(self.footer.get("font_size_pt", 8.0))
        align = self.footer.get("alignment", "center")
        pos = self.footer.get("position", "bottom_inside")

        if pos == "bottom_bar":
            c.setFillColor(tint_cmyk(self.colors.get("decorative_color"), 0.14))
            c.rect(self.px(x0), self.py(fy_top + 3.5), w * mm, 7.5 * mm, fill=1, stroke=0)

        logo_url = self.footer.get("logo_url", "")
        logo_w = float(self.footer.get("logo_width_mm", 20.0))
        logo_h = float(self.footer.get("logo_height_mm", 8.0))

        # Renderiza logotipo se houver
        has_logo = False
        if logo_url:
            if align == "left":
                lx = x0
            elif align == "right":
                lx = x0 + w - logo_w
            elif align == "split":
                lx = x0
            else:
                lx = x0 + (w - logo_w) / 2.0
            ly = fy_top - logo_h * 0.55 - (3.5 if footer_text and align != "split" else 0.0)
            has_logo = self._draw_graphic_asset(c, logo_url, lx, ly, logo_w, logo_h)

        if footer_text:
            c.setFillColor(text_col)
            c.setFont(font_name, font_size)
            text_y = fy_top + 1.5
            if align == "left":
                tx = x0 + (logo_w + 3.0 if (has_logo and align == "split") else 0.0)
                c.drawString(self.px(tx), self.py(text_y), footer_text)
            elif align == "right":
                c.drawRightString(self.px(x0 + w), self.py(text_y), footer_text)
            elif align == "split":
                c.drawRightString(self.px(x0 + w), self.py(text_y), footer_text)
            else:
                c.drawCentredString(self.px(x0 + w / 2.0), self.py(text_y), footer_text)
        c.restoreState()

    def _draw_graphic_asset(self, c: canvas.Canvas, url: str, x_mm: float, y_top_mm: float, w_mm: float, h_mm: float) -> bool:
        svg_res = self.cache.get_svg(url)
        if svg_res:
            drawing, vw, vh = svg_res
            if vw > 0 and vh > 0:
                sx = (w_mm * mm) / vw
                sy = (h_mm * mm) / vh
                scale = min(sx, sy)
                dx = self.px(x_mm) + ((w_mm * mm) - vw * scale) / 2.0
                dy = self.py(y_top_mm + h_mm) + ((h_mm * mm) - vh * scale) / 2.0
                c.saveState()
                c.translate(dx, dy)
                c.scale(scale, scale)
                renderPDF.draw(drawing, c, 0, 0)
                c.restoreState()
                return True

        img_res = self.cache.get_image(url)
        if img_res:
            reader, _, _ = img_res
            c.drawImage(
                reader,
                self.px(x_mm),
                self.py(y_top_mm + h_mm),
                width=w_mm * mm,
                height=h_mm * mm,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
            return True
        return False

    def _draw_element(self, c: canvas.Canvas, el: dict[str, Any]) -> None:
        c.saveState()
        x = float(el.get("x_mm", 20.0))
        y = float(el.get("y_mm", 20.0))
        w = max(2.0, float(el.get("width_mm", 60.0)))
        h = max(2.0, float(el.get("height_mm", 12.0)))
        rot = float(el.get("rotation_deg", 0.0))
        opacity = max(0.05, min(1.0, float(el.get("opacity", 1.0))))

        # Rotação em torno do centro exato da caixa
        cx_pt = self.px(x + w / 2.0)
        cy_pt = self.py(y + h / 2.0)
        c.translate(cx_pt, cy_pt)
        if abs(rot) > 0.01:
            c.rotate(-rot)

        # Desenha em coordenadas locais centradas em (0, 0)
        lx = -(w * mm) / 2.0
        ly = -(h * mm) / 2.0
        lw = w * mm
        lh = h * mm

        bg_col = el.get("bg_color")
        border_col = el.get("border_color")
        border_w = float(el.get("border_width_pt", 0.0))

        el_type = el.get("type", "phrase")

        if el_type == "shape":
            stype = el.get("shape_type", "rect")
            fill_cmyk = to_cmyk(bg_col or el.get("color"), alpha=opacity) if (bg_col or stype != "line") else None
            stroke_cmyk = to_cmyk(border_col or el.get("color"), alpha=opacity)
            c.setLineWidth(max(0.5, border_w))
            if stype == "line" or stype == "divider":
                c.setStrokeColor(stroke_cmyk)
                c.line(lx, 0, lx + lw, 0)
            elif stype == "circle":
                if bg_col:
                    c.setFillColor(to_cmyk(bg_col, alpha=opacity))
                if border_w > 0:
                    c.setStrokeColor(stroke_cmyk)
                c.ellipse(lx, ly, lx + lw, ly + lh, fill=1 if bg_col else 0, stroke=1 if border_w > 0 else 0)
            else:
                if bg_col:
                    c.setFillColor(fill_cmyk)
                if border_w > 0:
                    c.setStrokeColor(stroke_cmyk)
                rad = 2.5 * mm if stype == "rounded_rect" else 0.0
                c.roundRect(lx, ly, lw, lh, rad, fill=1 if bg_col else 0, stroke=1 if border_w > 0 else 0)
            c.restoreState()
            return

        if el_type == "image" and el.get("image_url"):
            # Reutiliza desenho local centralizado
            url = el["image_url"]
            svg_res = self.cache.get_svg(url)
            if svg_res:
                drawing, vw, vh = svg_res
                if vw > 0 and vh > 0:
                    scale = min(lw / vw, lh / vh)
                    dx = lx + (lw - vw * scale) / 2.0
                    dy = ly + (lh - vh * scale) / 2.0
                    c.saveState()
                    c.translate(dx, dy)
                    c.scale(scale, scale)
                    renderPDF.draw(drawing, c, 0, 0)
                    c.restoreState()
            else:
                img_res = self.cache.get_image(url)
                if img_res:
                    reader, _, _ = img_res
                    c.drawImage(reader, lx, ly, width=lw, height=lh, preserveAspectRatio=True, anchor="c", mask="auto")
            c.restoreState()
            return

        # Caixa de fundo / borda opcional para frases
        if bg_col or border_w > 0:
            if bg_col:
                c.setFillColor(to_cmyk(bg_col, alpha=opacity))
            if border_w > 0:
                c.setStrokeColor(to_cmyk(border_col or el.get("color"), alpha=opacity))
                c.setLineWidth(border_w)
            c.roundRect(lx, ly, lw, lh, 1.5 * mm, fill=1 if bg_col else 0, stroke=1 if border_w > 0 else 0)

        # Texto da frase
        text = el.get("resolved_text") if el.get("resolved_text") is not None else el.get("text", "")
        if text:
            font_name = resolve_font(
                el.get("font_family", "Georgia"),
                bold=bool(el.get("bold", False)),
                italic=bool(el.get("italic", False)),
            )
            font_size = float(el.get("font_size_pt", 10.0))
            align = el.get("alignment", "center")
            text_col = to_cmyk(el.get("color"), alpha=opacity)
            pad = 1.5 * mm
            max_tw = max(4.0, lw - 2 * pad)
            lines = _wrap_text(c, text, font_name, font_size, max_tw)
            line_h = font_size * 1.28
            total_th = len(lines) * line_h
            # Centraliza verticalmente dentro da caixa
            start_y = (total_th / 2.0) - font_size * 0.85

            c.setFillColor(text_col)
            c.setFont(font_name, font_size)
            for li, line in enumerate(lines):
                ty = start_y - li * line_h
                if align == "left":
                    c.drawString(lx + pad, ty, line)
                elif align == "right":
                    c.drawRightString(lx + lw - pad, ty, line)
                else:
                    c.drawCentredString(0, ty, line)

                if el.get("underline") and line.strip():
                    tw = pdfmetrics.stringWidth(line, font_name, font_size)
                    if align == "left":
                        ux0 = lx + pad
                    elif align == "right":
                        ux0 = lx + lw - pad - tw
                    else:
                        ux0 = -tw / 2.0
                    c.setStrokeColor(text_col)
                    c.setLineWidth(max(0.4, font_size * 0.06))
                    c.line(ux0, ty - 1.5, ux0 + tw, ty - 1.5)

        c.restoreState()


def render_pages_to_pdf_bytes(
    config: dict[str, Any],
    pages: list[dict[str, Any]],
    include_bleed: bool = True,
    include_crop_marks: bool = False,
    mirror_margins: bool = True,
    cache: ResourceCache | None = None,
    title: str = "Agenda Personalizada",
) -> bytes:
    """Renderiza uma lista de páginas para bytes de um arquivo PDF CMYK."""
    buf = io.BytesIO()
    renderer = AgendaPDFRenderer(
        config=config,
        include_bleed=include_bleed,
        include_crop_marks=include_crop_marks,
        mirror_margins=mirror_margins,
        cache=cache,
    )
    c = canvas.Canvas(buf, pagesize=(renderer.media_w_mm * mm, renderer.media_h_mm * mm))
    c.setTitle(title)
    c.setCreator("EditorGráfica Pro - Motor PDF CMYK")
    for p in pages:
        renderer.draw_page(c, p)
    c.save()
    return buf.getvalue()


def export_project_bundle(
    config: dict[str, Any],
    export_mode: str = "single_pdf",
    include_bleed: bool = True,
    include_crop_marks: bool = False,
    mirror_margins: bool = True,
    page_range: str = "",
    project_name: str = "Agenda",
    recipient: dict[str, str] | None = None,
    cache: ResourceCache | None = None,
) -> tuple[bytes, str, str]:
    """Gera o arquivo final (PDF ou ZIP) segundo um dos modos profissionais de exportação."""
    cfg_copy = dict(config)
    ps_copy = dict(cfg_copy.get("page_setup", {}))
    ps_copy["mirror_margins"] = mirror_margins
    cfg_copy["page_setup"] = ps_copy

    generated = generate_agenda_pages(cfg_copy, recipient=recipient)
    pages = generated["pages"]

    if page_range and page_range.strip():
        allowed = parse_page_list(page_range, len(pages))
        if allowed:
            pages = [p for p in pages if p["page_number"] in allowed]

    cache = cache or ResourceCache()
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", project_name).strip("_") or "Agenda"

    if export_mode == "single_pdf":
        pdf_bytes = render_pages_to_pdf_bytes(
            cfg_copy,
            pages,
            include_bleed=include_bleed,
            include_crop_marks=include_crop_marks,
            mirror_margins=mirror_margins,
            cache=cache,
            title=project_name,
        )
        return (pdf_bytes, "application/pdf", f"{safe_name}.pdf")

    if export_mode == "by_month":
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            special_front = [p for p in pages if p["page_type"].startswith("special_") and p["page_type"] != "special_notes"]
            if special_front:
                zf.writestr(
                    "00_Paginas_Especiais.pdf",
                    render_pages_to_pdf_bytes(
                        cfg_copy, special_front, include_bleed, include_crop_marks, mirror_margins, cache, f"{project_name} - Especiais"
                    ),
                )
            for mo in range(1, 13):
                mo_pages = [p for p in pages if p.get("month") == mo]
                if mo_pages:
                    mo_name = MONTH_NAMES_PT[mo].replace("ç", "c").replace("Ç", "C")
                    zf.writestr(
                        f"{mo:02d}_{mo_name}.pdf",
                        render_pages_to_pdf_bytes(
                            cfg_copy, mo_pages, include_bleed, include_crop_marks, mirror_margins, cache, f"{project_name} - {MONTH_NAMES_PT[mo]}"
                        ),
                    )
            special_end = [p for p in pages if p["page_type"] == "special_notes"]
            if special_end:
                zf.writestr(
                    "13_Anotacoes_Finais.pdf",
                    render_pages_to_pdf_bytes(
                        cfg_copy, special_end, include_bleed, include_crop_marks, mirror_margins, cache, f"{project_name} - Notas"
                    ),
                )
        return (zip_buf.getvalue(), "application/zip", f"{safe_name}_por_mes.zip")

    if export_mode == "individual_pages":
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in pages:
                p_bytes = render_pages_to_pdf_bytes(
                    cfg_copy, [p], include_bleed, include_crop_marks, mirror_margins, cache, f"{project_name} - Pág {p['page_number']}"
                )
                zf.writestr(f"Pagina_{p['page_number']:04d}.pdf", p_bytes)
        return (zip_buf.getvalue(), "application/zip", f"{safe_name}_paginas_individuais.zip")

    raise ValueError(f"Modo de exportação desconhecido: {export_mode}")


def export_batch_personalized_zip(
    config: dict[str, Any],
    recipients: list[dict[str, str]],
    include_bleed: bool = True,
    include_crop_marks: bool = False,
    mirror_margins: bool = True,
    page_range: str = "",
    project_name: str = "Agenda",
) -> bytes:
    """Gera um pacote ZIP com um PDF completo personalizado por destinatário (personalização em massa)."""
    cache = ResourceCache()
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, rec in enumerate(recipients, start=1):
            nome = rec.get("nome") or f"Cliente_{idx}"
            safe_rec = re.sub(r"[^A-Za-z0-9_-]+", "_", nome).strip("_") or f"Cliente_{idx}"
            pdf_bytes, _, _ = export_project_bundle(
                config=config,
                export_mode="single_pdf",
                include_bleed=include_bleed,
                include_crop_marks=include_crop_marks,
                mirror_margins=mirror_margins,
                page_range=page_range,
                project_name=f"{project_name} - {nome}",
                recipient=rec,
                cache=cache,
            )
            zf.writestr(f"{idx:03d}_{safe_rec}.pdf", pdf_bytes)
    return zip_buf.getvalue()
