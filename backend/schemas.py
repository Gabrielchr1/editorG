"""Schemas Pydantic, conversões CMYK e configuração padrão de projetos."""

from __future__ import annotations

import copy
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def cmyk_to_hex(c: float, m: float, y: float, k: float) -> str:
    """Converte percentuais CMYK (0..100) para preview hexadecimal RGB sRGB."""
    c_f = max(0.0, min(100.0, float(c))) / 100.0
    m_f = max(0.0, min(100.0, float(m))) / 100.0
    y_f = max(0.0, min(100.0, float(y))) / 100.0
    k_f = max(0.0, min(100.0, float(k))) / 100.0
    r = round(255.0 * (1.0 - c_f) * (1.0 - k_f))
    g = round(255.0 * (1.0 - m_f) * (1.0 - k_f))
    b = round(255.0 * (1.0 - y_f) * (1.0 - k_f))
    return f"#{r:02X}{g:02X}{b:02X}"


def hex_to_cmyk(hex_color: str) -> tuple[int, int, int, int]:
    """Converte hexadecimal RGB para aproximação CMYK inteira (0..100)."""
    clean = hex_color.strip().lstrip("#")
    if len(clean) == 3:
        clean = "".join(ch * 2 for ch in clean)
    if len(clean) != 6:
        return (0, 0, 0, 100)
    r = int(clean[0:2], 16) / 255.0
    g = int(clean[2:4], 16) / 255.0
    b = int(clean[4:6], 16) / 255.0
    k = 1.0 - max(r, g, b)
    if k >= 0.9999:
        return (0, 0, 0, 100)
    c = (1.0 - r - k) / (1.0 - k)
    m = (1.0 - g - k) / (1.0 - k)
    y = (1.0 - b - k) / (1.0 - k)
    return (round(c * 100), round(m * 100), round(y * 100), round(k * 100))


class CMYKColor(BaseModel):
    c: int = Field(0, ge=0, le=100)
    m: int = Field(0, ge=0, le=100)
    y: int = Field(0, ge=0, le=100)
    k: int = Field(100, ge=0, le=100)
    hex: str = "#000000"

    @model_validator(mode="after")
    def sync_hex(self) -> "CMYKColor":
        self.hex = cmyk_to_hex(self.c, self.m, self.y, self.k)
        return self


def make_cmyk(c: int, m: int, y: int, k: int) -> dict[str, Any]:
    return {"c": c, "m": m, "y": y, "k": k, "hex": cmyk_to_hex(c, m, y, k)}


class PageSetup(BaseModel):
    width_mm: float = Field(150.0, ge=60.0, le=500.0)
    height_mm: float = Field(210.0, ge=80.0, le=600.0)
    orientation: Literal["portrait", "landscape"] = "portrait"
    bleed_mm: float = Field(3.0, ge=0.0, le=20.0)
    safety_margin_mm: float = Field(5.0, ge=0.0, le=30.0)
    margin_top_mm: float = Field(12.0, ge=2.0, le=50.0)
    margin_bottom_mm: float = Field(12.0, ge=2.0, le=50.0)
    margin_inner_mm: float = Field(18.0, ge=2.0, le=60.0)
    margin_outer_mm: float = Field(10.0, ge=2.0, le=50.0)
    mirror_margins: bool = True
    show_crop_marks: bool = False
    show_bleed_guide: bool = True
    show_safety_guide: bool = True
    show_margin_guide: bool = True
    show_grid: bool = False
    grid_size_mm: float = Field(5.0, ge=1.0, le=50.0)


class CustomHoliday(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    date: str  # YYYY-MM-DD ou MM-DD
    name: str
    type: Literal["national", "state", "municipal", "commemorative"] = "commemorative"
    recurring: bool = True


class CalendarConfig(BaseModel):
    year: int = Field(2026, ge=1900, le=2150)
    start_date: str = "2026-01-01"
    end_date: str = "2026-12-31"
    is_dated: bool = True
    layout_mode: Literal[
        "1_dpp",
        "2_dpp",
        "weekly",
        "monthly",
        "financial",
        "corporate",
        "planner",
    ] = "1_dpp"
    weekend_mode: Literal["together", "separate"] = "together"
    week_starts_on: Literal[0, 1] = 0  # 0=Domingo, 1=Segunda
    month_display_style: Literal[
        "full_upper",
        "full_title",
        "short_upper",
        "num_full",
    ] = "full_upper"
    show_mini_calendar: bool = True
    include_month_openers: bool = True
    highlight_national_holidays: bool = True
    state_code: str = ""
    custom_holidays: list[CustomHoliday] = Field(default_factory=list)


class ColorThemeCMYK(BaseModel):
    palette_name: str = "Clássico Executivo"
    title_color: CMYKColor = Field(default_factory=lambda: CMYKColor(**make_cmyk(85, 65, 25, 35)))
    weekday_color: CMYKColor = Field(default_factory=lambda: CMYKColor(**make_cmyk(60, 45, 30, 15)))
    date_number_color: CMYKColor = Field(default_factory=lambda: CMYKColor(**make_cmyk(90, 70, 20, 40)))
    ruling_line_color: CMYKColor = Field(default_factory=lambda: CMYKColor(**make_cmyk(0, 0, 0, 25)))
    decorative_color: CMYKColor = Field(default_factory=lambda: CMYKColor(**make_cmyk(30, 20, 5, 5)))
    highlight_color: CMYKColor = Field(default_factory=lambda: CMYKColor(**make_cmyk(15, 35, 85, 5)))
    weekend_color: CMYKColor = Field(default_factory=lambda: CMYKColor(**make_cmyk(10, 75, 70, 10)))
    holiday_color: CMYKColor = Field(default_factory=lambda: CMYKColor(**make_cmyk(0, 90, 80, 10)))
    background_color: CMYKColor = Field(default_factory=lambda: CMYKColor(**make_cmyk(0, 0, 0, 0)))


class RulingConfig(BaseModel):
    ruling_type: Literal["horizontal", "dotted", "grid", "blank", "custom"] = "horizontal"
    line_spacing_mm: float = Field(7.0, ge=2.5, le=30.0)
    line_thickness_pt: float = Field(0.5, ge=0.1, le=5.0)
    line_color: CMYKColor = Field(default_factory=lambda: CMYKColor(**make_cmyk(0, 0, 0, 25)))
    line_count_mode: Literal["auto", "fixed"] = "auto"
    fixed_line_count: int = Field(22, ge=1, le=80)
    margin_top_offset_mm: float = Field(28.0, ge=0.0, le=120.0)
    margin_bottom_offset_mm: float = Field(14.0, ge=0.0, le=80.0)
    margin_left_offset_mm: float = Field(0.0, ge=0.0, le=50.0)
    margin_right_offset_mm: float = Field(0.0, ge=0.0, le=50.0)
    show_time_column: bool = True
    time_start_hour: int = Field(7, ge=0, le=23)
    time_end_hour: int = Field(21, ge=1, le=23)
    time_interval_min: Literal[30, 60] = 60
    show_checkboxes: bool = False
    custom_columns: int = Field(1, ge=1, le=4)
    show_priorities_box: bool = False
    show_notes_section: bool = False


class FooterConfig(BaseModel):
    enabled: bool = True
    company_name: str = ""
    professional_name: str = ""
    extra_text: str = ""
    logo_url: str = ""
    logo_width_mm: float = Field(22.0, ge=4.0, le=120.0)
    logo_height_mm: float = Field(10.0, ge=4.0, le=60.0)
    position: Literal["bottom_inside", "below_ruling", "bottom_bar"] = "bottom_inside"
    alignment: Literal["left", "center", "right", "split"] = "center"
    font_family: str = "Arial"
    font_size_pt: float = Field(8.0, ge=5.0, le=24.0)
    bold: bool = False
    italic: bool = False
    text_color: CMYKColor = Field(default_factory=lambda: CMYKColor(**make_cmyk(0, 0, 0, 60)))
    distance_from_bottom_mm: float = Field(8.0, ge=2.0, le=40.0)
    apply_to: Literal[
        "all",
        "daily_only",
        "odd",
        "even",
        "month_openers",
        "weekdays",
        "weekends",
        "specific_pages",
    ] = "all"
    specific_pages: str = ""


class CanvasElement(BaseModel):
    id: str = Field(default_factory=lambda: f"el_{uuid4().hex[:8]}")
    type: Literal["phrase", "image", "shape"] = "phrase"
    label: str = ""
    text: str = ""
    image_url: str = ""
    shape_type: Literal["rect", "rounded_rect", "line", "circle", "divider"] = "rect"
    x_mm: float = 24.0
    y_mm: float = 175.0
    width_mm: float = 104.0
    height_mm: float = 14.0
    rotation_deg: float = Field(0.0, ge=-360.0, le=360.0)
    font_family: str = "Georgia"
    font_size_pt: float = Field(9.5, ge=5.0, le=72.0)
    bold: bool = False
    italic: bool = True
    underline: bool = False
    alignment: Literal["left", "center", "right", "justify"] = "center"
    color: CMYKColor = Field(default_factory=lambda: CMYKColor(**make_cmyk(60, 45, 25, 20)))
    bg_color: Optional[CMYKColor] = None
    border_color: Optional[CMYKColor] = None
    border_width_pt: float = Field(0.0, ge=0.0, le=10.0)
    opacity: float = Field(1.0, ge=0.05, le=1.0)
    z_index: int = 10
    locked: bool = False
    target_rule: Literal[
        "all",
        "specific_pages",
        "weekdays",
        "weekends",
        "specific_dates",
        "month_openers",
        "daily_only",
    ] = "all"
    target_pages: str = ""
    target_weekdays: list[int] = Field(default_factory=list)
    target_dates: list[str] = Field(default_factory=list)
    target_months: list[int] = Field(default_factory=list)


class SpecialPagesConfig(BaseModel):
    cover_page: bool = True
    cover_title: str = "AGENDA 2026"
    cover_subtitle: str = "Planejamento Profissional & Pessoal"
    personal_data: bool = True
    annual_calendar: bool = True
    annual_planner: bool = True
    goals_page: bool = True
    financial_summary: bool = False
    birthdays_page: bool = True
    contacts_page: bool = True
    notes_end_pages: int = Field(2, ge=0, le=40)


class ExportConfig(BaseModel):
    export_mode: Literal[
        "single_pdf",
        "by_month",
        "individual_pages",
        "batch_personalized",
    ] = "single_pdf"
    include_bleed: bool = True
    include_crop_marks: bool = False
    mirror_margins: bool = True
    page_range: str = ""
    header_font_family: str = "Georgia"
    body_font_family: str = "Arial"


class ProjectConfig(BaseModel):
    page_setup: PageSetup = Field(default_factory=PageSetup)
    calendar: CalendarConfig = Field(default_factory=CalendarConfig)
    colors: ColorThemeCMYK = Field(default_factory=ColorThemeCMYK)
    ruling: RulingConfig = Field(default_factory=RulingConfig)
    footer: FooterConfig = Field(default_factory=FooterConfig)
    elements: list[CanvasElement] = Field(default_factory=list)
    special_pages: SpecialPagesConfig = Field(default_factory=SpecialPagesConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)


def default_project_config() -> dict[str, Any]:
    """Retorna a configuração padrão validada como dicionário serializável."""
    return copy.deepcopy(ProjectConfig().model_dump())


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    client_name: str = ""
    description: str = ""
    template_id: Optional[str] = None
    config: Optional[dict[str, Any]] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    client_name: Optional[str] = None
    description: Optional[str] = None
    is_favorite: Optional[int] = None
    config: Optional[dict[str, Any]] = None


class ProjectDuplicateRequest(BaseModel):
    new_name: Optional[str] = None
    new_client_name: Optional[str] = None


class LibraryItemCreate(BaseModel):
    category: Literal["logo", "phrase", "palette", "graphic", "font"]
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    tags: str = ""
    content_json: dict[str, Any] = Field(default_factory=dict)
    file_path: str = ""


class ExportRequest(BaseModel):
    export_mode: Literal["single_pdf", "by_month", "individual_pages"] = "single_pdf"
    include_bleed: bool = True
    include_crop_marks: bool = False
    mirror_margins: bool = True
    page_range: str = ""
    config_override: Optional[dict[str, Any]] = None


class BatchRecipient(BaseModel):
    nome: str = Field(..., min_length=1)
    empresa: str = ""
    cargo: str = ""
    extra: str = ""


class BatchExportRequest(BaseModel):
    recipients: list[BatchRecipient] = Field(..., min_length=1, max_length=500)
    include_bleed: bool = True
    include_crop_marks: bool = False
    mirror_margins: bool = True
    page_range: str = ""
    config_override: Optional[dict[str, Any]] = None
