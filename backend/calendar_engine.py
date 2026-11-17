"""Motor de calendário exato para agendas datadas e permanentes."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any


MONTH_NAMES_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

MONTH_SHORT_PT = {
    1: "JAN",
    2: "FEV",
    3: "MAR",
    4: "ABR",
    5: "MAI",
    6: "JUN",
    7: "JUL",
    8: "AGO",
    9: "SET",
    10: "OUT",
    11: "NOV",
    12: "DEZ",
}

# Padronizado: 0 = Domingo .. 6 = Sábado
WEEKDAY_NAMES_PT = {
    0: "Domingo",
    1: "Segunda-feira",
    2: "Terça-feira",
    3: "Quarta-feira",
    4: "Quinta-feira",
    5: "Sexta-feira",
    6: "Sábado",
}

WEEKDAY_SHORT_PT = {
    0: "DOM",
    1: "SEG",
    2: "TER",
    3: "QUA",
    4: "QUI",
    5: "SEX",
    6: "SÁB",
}

WEEKDAY_INITIAL_PT = {
    0: "D",
    1: "S",
    2: "T",
    3: "Q",
    4: "Q",
    5: "S",
    6: "S",
}

FIXED_NATIONAL_HOLIDAYS_BR: dict[str, str] = {
    "01-01": "Confraternização Universal",
    "04-21": "Tiradentes",
    "05-01": "Dia do Trabalho",
    "09-07": "Independência do Brasil",
    "10-12": "Nossa Senhora Aparecida",
    "11-02": "Finados",
    "11-15": "Proclamação da República",
    "11-20": "Dia da Consciência Negra",
    "12-25": "Natal",
}

STATE_HOLIDAYS_BR: dict[str, list[dict[str, str]]] = {
    "AC": [
        {"date": "01-23", "name": "Dia do Evangélico (AC)"},
        {"date": "06-15", "name": "Aniversário do Acre"},
        {"date": "09-05", "name": "Dia da Amazônia"},
        {"date": "11-17", "name": "Tratado de Petrópolis (AC)"},
    ],
    "AL": [
        {"date": "06-24", "name": "São João (AL)"},
        {"date": "06-29", "name": "São Pedro (AL)"},
        {"date": "09-16", "name": "Emancipação Política de Alagoas"},
    ],
    "AM": [
        {"date": "09-05", "name": "Elevação do Amazonas"},
        {"date": "12-08", "name": "Nossa Senhora da Conceição (AM)"},
    ],
    "AP": [
        {"date": "03-19", "name": "Dia de São José (AP)"},
        {"date": "09-13", "name": "Criação do Território do Amapá"},
    ],
    "BA": [{"date": "07-02", "name": "Independência da Bahia"}],
    "CE": [
        {"date": "03-19", "name": "Dia de São José (CE)"},
        {"date": "03-25", "name": "Data Magna do Ceará"},
    ],
    "DF": [{"date": "04-21", "name": "Fundação de Brasília"}],
    "ES": [{"date": "04-12", "name": "Nossa Senhora da Penha (ES)"}],
    "GO": [{"date": "10-24", "name": "Pedra Fundamental de Goiânia"}],
    "MA": [{"date": "07-28", "name": "Adesão do Maranhão à Independência"}],
    "MG": [{"date": "04-21", "name": "Data Magna de Minas Gerais"}],
    "MS": [{"date": "10-11", "name": "Criação do Mato Grosso do Sul"}],
    "MT": [{"date": "11-20", "name": "Consciência Negra (MT)"}],
    "PA": [{"date": "08-15", "name": "Adesão do Pará à Independência"}],
    "PB": [{"date": "08-05", "name": "Fundação do Estado da Paraíba"}],
    "PE": [{"date": "03-06", "name": "Revolução Pernambucana"}],
    "PI": [{"date": "10-19", "name": "Dia do Piauí"}],
    "PR": [{"date": "12-19", "name": "Emancipação Política do Paraná"}],
    "RJ": [
        {"date": "04-23", "name": "Dia de São Jorge (RJ)"},
        {"date": "10-15", "name": "Dia do Comércio (RJ)"},
    ],
    "RN": [{"date": "10-03", "name": "Mártires de Cunhaú e Uruaçu (RN)"}],
    "RO": [{"date": "01-04", "name": "Criação de Rondônia"}],
    "RR": [{"date": "10-05", "name": "Criação de Roraima"}],
    "RS": [{"date": "09-20", "name": "Revolução Farroupilha (RS)"}],
    "SC": [{"date": "08-11", "name": "Criação da Capitania de SC"}],
    "SE": [{"date": "07-08", "name": "Emancipação Política de Sergipe"}],
    "SP": [{"date": "07-09", "name": "Revolução Constitucionalista (SP)"}],
    "TO": [{"date": "10-05", "name": "Criação do Tocantins"}],
}


def compute_easter(year: int) -> date:
    """Calcula a data exata da Páscoa (calendário gregoriano) usando Meeus/Jones/Butcher."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_national_holidays_for_year(year: int) -> dict[str, list[dict[str, str]]]:
    """Retorna mapa ISO -> lista de feriados nacionais fixos e móveis para o ano."""
    result: dict[str, list[dict[str, str]]] = {}

    def add(dt: date, name: str, htype: str = "national") -> None:
        iso = dt.isoformat()
        result.setdefault(iso, []).append({"name": name, "type": htype})

    for mm_dd, name in FIXED_NATIONAL_HOLIDAYS_BR.items():
        mm, dd = map(int, mm_dd.split("-"))
        add(date(year, mm, dd), name, "national")

    easter = compute_easter(year)
    add(easter - timedelta(days=48), "Carnaval (Segunda-feira)", "national")
    add(easter - timedelta(days=47), "Carnaval (Terça-feira)", "national")
    add(easter - timedelta(days=2), "Sexta-feira Santa", "national")
    add(easter, "Páscoa", "national")
    add(easter + timedelta(days=60), "Corpus Christi", "national")
    return result


def to_sun0_weekday(dt: date) -> int:
    """Converte Python weekday (0=Seg..6=Dom) para 0=Dom..6=Sáb."""
    return (dt.weekday() + 1) % 7


def format_month_label(month: int, year: int | None, style: str) -> str:
    """Formata o nome do mês conforme configuração de exibição."""
    name = MONTH_NAMES_PT.get(month, str(month))
    short = MONTH_SHORT_PT.get(month, str(month))
    if style == "full_upper":
        return name.upper()
    if style == "full_title":
        return name
    if style == "short_upper":
        return short
    if style == "num_full":
        return f"{month:02d} • {name.upper()}"
    return name.upper()


def build_mini_calendar(year: int, month: int, week_starts_on: int = 0) -> dict[str, Any]:
    """Constrói a matriz do mini-calendário do mês respeitando o dia de início da semana."""
    # Python calendar: 0=Monday .. 6=Sunday
    firstweekday_py = 6 if week_starts_on == 0 else 0
    cal = calendar.Calendar(firstweekday=firstweekday_py)
    weeks = cal.monthdayscalendar(year, month)
    if week_starts_on == 0:
        headers = ["D", "S", "T", "Q", "Q", "S", "S"]
    else:
        headers = ["S", "T", "Q", "Q", "S", "S", "D"]
    return {
        "year": year,
        "month": month,
        "month_name": MONTH_NAMES_PT[month],
        "headers": headers,
        "weeks": weeks,
    }


def parse_page_list(spec: str, max_page: int = 2000) -> set[int]:
    """Interpreta string como '1, 3, 5-10' para conjunto de números de página."""
    pages: set[int] = set()
    if not spec or not spec.strip():
        return pages
    for chunk in spec.split(","):
        part = chunk.strip()
        if not part:
            continue
        if "-" in part:
            bounds = part.split("-", 1)
            try:
                start = max(1, int(bounds[0].strip()))
                end = min(max_page, int(bounds[1].strip()))
                if start <= end:
                    pages.update(range(start, end + 1))
            except ValueError:
                continue
        else:
            try:
                num = int(part)
                if 1 <= num <= max_page:
                    pages.add(num)
            except ValueError:
                continue
    return pages


def _build_holiday_lookup(
    years: set[int],
    include_national: bool,
    state_code: str,
    custom_holidays: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    """Constrói mapa completo de feriados por ISO (YYYY-MM-DD) e recorrente (MM-DD)."""
    lookup: dict[str, list[dict[str, str]]] = {}

    def add_iso(iso: str, name: str, htype: str) -> None:
        items = lookup.setdefault(iso, [])
        if not any(it["name"] == name for it in items):
            items.append({"name": name, "type": htype})

    if include_national:
        for yr in years:
            nat = get_national_holidays_for_year(yr)
            for iso, items in nat.items():
                for item in items:
                    add_iso(iso, item["name"], item["type"])

    uf = (state_code or "").strip().upper()
    if uf and uf in STATE_HOLIDAYS_BR:
        for yr in years:
            for item in STATE_HOLIDAYS_BR[uf]:
                mm, dd = map(int, item["date"].split("-"))
                try:
                    iso = date(yr, mm, dd).isoformat()
                    add_iso(iso, item["name"], "state")
                except ValueError:
                    continue

    for ch in custom_holidays or []:
        raw_date = str(ch.get("date", "")).strip()
        name = str(ch.get("name", "")).strip()
        htype = str(ch.get("type", "commemorative")).strip() or "commemorative"
        if not raw_date or not name:
            continue
        parts = raw_date.split("-")
        if len(parts) == 3:
            # YYYY-MM-DD ou recorrente se recurring=True
            try:
                y_val, m_val, d_val = int(parts[0]), int(parts[1]), int(parts[2])
                if ch.get("recurring", False):
                    for yr in years:
                        try:
                            add_iso(date(yr, m_val, d_val).isoformat(), name, htype)
                        except ValueError:
                            continue
                else:
                    add_iso(date(y_val, m_val, d_val).isoformat(), name, htype)
            except ValueError:
                continue
        elif len(parts) == 2:
            try:
                m_val, d_val = int(parts[0]), int(parts[1])
                for yr in years:
                    try:
                        add_iso(date(yr, m_val, d_val).isoformat(), name, htype)
                    except ValueError:
                        continue
            except ValueError:
                continue

    return lookup


def _make_dated_entry(dt: date, holiday_lookup: dict[str, list[dict[str, str]]], month_style: str) -> dict[str, Any]:
    wd = to_sun0_weekday(dt)
    year_start = date(dt.year, 1, 1)
    year_end = date(dt.year, 12, 31)
    day_of_year = (dt - year_start).days + 1
    days_in_year = (year_end - year_start).days + 1
    iso = dt.isoformat()
    holidays = holiday_lookup.get(iso, [])
    return {
        "iso": iso,
        "day": dt.day,
        "month": dt.month,
        "year": dt.year,
        "month_name": MONTH_NAMES_PT[dt.month],
        "month_label": format_month_label(dt.month, dt.year, month_style),
        "weekday_num": wd,
        "weekday_name": WEEKDAY_NAMES_PT[wd],
        "weekday_short": WEEKDAY_SHORT_PT[wd],
        "is_weekend": wd in (0, 6),
        "holidays": holidays,
        "has_holiday": len(holidays) > 0,
        "day_of_year": day_of_year,
        "days_remaining": days_in_year - day_of_year,
        "is_dated": True,
    }


def _make_undated_entry(month: int, day: int, month_style: str, idx: int) -> dict[str, Any]:
    return {
        "iso": f"PERM-{month:02d}-{day:02d}",
        "day": day,
        "month": month,
        "year": None,
        "month_name": MONTH_NAMES_PT[month],
        "month_label": format_month_label(month, None, month_style),
        "weekday_num": None,
        "weekday_name": "D • S • T • Q • Q • S • S",
        "weekday_short": "PERM",
        "is_weekend": False,
        "holidays": [],
        "has_holiday": False,
        "day_of_year": idx,
        "days_remaining": 366 - idx,
        "is_dated": False,
    }


def _should_show_element(el: dict[str, Any], page: dict[str, Any], max_pages: int) -> bool:
    rule = el.get("target_rule", "all")
    page_type = page["page_type"]
    page_num = page["page_number"]
    dates = page.get("dates", [])
    month = page.get("month")

    # Filtro opcional de meses específicos combinado com qualquer regra
    target_months = el.get("target_months") or []
    if target_months:
        if month is None or int(month) not in [int(m) for m in target_months]:
            return False

    if rule == "all":
        return True

    if rule == "daily_only":
        return not page_type.startswith("special_") and page_type != "month_opener"

    if rule == "month_openers":
        return page_type == "month_opener"

    if rule == "specific_pages":
        allowed = parse_page_list(str(el.get("target_pages", "")), max_pages)
        return page_num in allowed

    if rule == "weekdays":
        if not dates:
            return False
        target_wds = el.get("target_weekdays") or [1, 2, 3, 4, 5]
        return any(d.get("weekday_num") in target_wds for d in dates if d.get("weekday_num") is not None)

    if rule == "weekends":
        if not dates:
            return False
        return any(d.get("is_weekend") for d in dates)

    if rule == "specific_dates":
        if not dates:
            return False
        targets = {str(t).strip() for t in (el.get("target_dates") or []) if str(t).strip()}
        for d in dates:
            iso = str(d.get("iso", ""))
            mm_dd = f"{int(d['month']):02d}-{int(d['day']):02d}"
            dd_mm_slash = f"{int(d['day']):02d}/{int(d['month']):02d}"
            if iso in targets or mm_dd in targets or dd_mm_slash in targets:
                return True
        return False

    return True


def _should_show_footer(footer: dict[str, Any], page: dict[str, Any], max_pages: int) -> bool:
    if not footer.get("enabled", True):
        return False
    page_type = page["page_type"]
    if page_type == "special_cover":
        return False
    apply_to = footer.get("apply_to", "all")
    page_num = page["page_number"]
    dates = page.get("dates", [])

    if apply_to == "all":
        return True
    if apply_to == "daily_only":
        return not page_type.startswith("special_") and page_type != "month_opener"
    if apply_to == "odd":
        return page_num % 2 == 1
    if apply_to == "even":
        return page_num % 2 == 0
    if apply_to == "month_openers":
        return page_type == "month_opener"
    if apply_to == "weekdays":
        return any((not d.get("is_weekend")) and d.get("weekday_num") is not None for d in dates)
    if apply_to == "weekends":
        return any(d.get("is_weekend") for d in dates)
    if apply_to == "specific_pages":
        return page_num in parse_page_list(str(footer.get("specific_pages", "")), max_pages)
    return True


def _resolve_template_vars(text: str, page: dict[str, Any], recipient: dict[str, str] | None = None) -> str:
    if not text or "{{" not in text:
        return text
    dates = page.get("dates") or []
    first_date = dates[0] if dates else {}
    month_num = page.get("month")
    month_name = MONTH_NAMES_PT.get(month_num, "") if month_num else ""
    year_val = page.get("year") or first_date.get("year") or ""
    holiday_names = ", ".join(h["name"] for d in dates for h in d.get("holidays", []))

    replacements = {
        "{{mes}}": month_name,
        "{{MES}}": month_name.upper(),
        "{{ano}}": str(year_val),
        "{{dia}}": f"{first_date.get('day'):02d}" if first_date.get("day") else "",
        "{{dia_semana}}": str(first_date.get("weekday_name", "")),
        "{{feriado}}": holiday_names,
        "{{pagina}}": str(page.get("page_number", "")),
        "{{nome_personalizado}}": (recipient or {}).get("nome", ""),
        "{{empresa_personalizada}}": (recipient or {}).get("empresa", ""),
        "{{cargo_personalizado}}": (recipient or {}).get("cargo", ""),
    }
    out = text
    for key, val in replacements.items():
        if key in out:
            out = out.replace(key, val)
    return out


def generate_agenda_pages(
    config: dict[str, Any],
    recipient: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Gera a estrutura paginada completa do miolo da agenda sem erros de calendário."""
    cal_cfg = config.get("calendar", {})
    page_setup = config.get("page_setup", {})
    special_cfg = config.get("special_pages", {})
    footer_cfg = config.get("footer", {})
    elements = config.get("elements", [])

    year = int(cal_cfg.get("year", 2026))
    is_dated = bool(cal_cfg.get("is_dated", True))
    layout_mode = cal_cfg.get("layout_mode", "1_dpp")
    weekend_mode = cal_cfg.get("weekend_mode", "together")
    week_starts_on = int(cal_cfg.get("week_starts_on", 0))
    month_style = cal_cfg.get("month_display_style", "full_upper")
    include_month_openers = bool(cal_cfg.get("include_month_openers", True))
    highlight_national = bool(cal_cfg.get("highlight_national_holidays", True))
    state_code = cal_cfg.get("state_code", "")
    custom_holidays = cal_cfg.get("custom_holidays", [])

    raw_pages: list[dict[str, Any]] = []

    # 1. Páginas Especiais Iniciais
    if special_cfg.get("cover_page", True):
        raw_pages.append(
            {
                "page_type": "special_cover",
                "title": special_cfg.get("cover_title") or f"AGENDA {year if is_dated else 'PERMANENTE'}",
                "subtitle": special_cfg.get("cover_subtitle") or "",
                "month": None,
                "year": year if is_dated else None,
                "dates": [],
            }
        )
    if special_cfg.get("personal_data", True):
        raw_pages.append(
            {
                "page_type": "special_personal",
                "title": "DADOS PESSOAIS",
                "month": None,
                "year": year if is_dated else None,
                "dates": [],
            }
        )
    if special_cfg.get("annual_calendar", True):
        raw_pages.append(
            {
                "page_type": "special_calendar",
                "title": f"CALENDÁRIO {year} & {year + 1}",
                "month": None,
                "year": year,
                "dates": [],
                "extra": {
                    "calendars_current": [build_mini_calendar(year, m, week_starts_on) for m in range(1, 13)],
                    "calendars_next": [build_mini_calendar(year + 1, m, week_starts_on) for m in range(1, 13)],
                },
            }
        )
    if special_cfg.get("annual_planner", True):
        raw_pages.append(
            {
                "page_type": "special_planner",
                "title": "PLANEJAMENTO ANUAL",
                "month": None,
                "year": year if is_dated else None,
                "dates": [],
            }
        )
    if special_cfg.get("goals_page", True):
        raw_pages.append(
            {
                "page_type": "special_goals",
                "title": "METAS & PROJETOS",
                "month": None,
                "year": year if is_dated else None,
                "dates": [],
            }
        )
    if special_cfg.get("financial_summary", False):
        raw_pages.append(
            {
                "page_type": "special_financial",
                "title": "PLANEJAMENTO FINANCEIRO ANUAL",
                "month": None,
                "year": year if is_dated else None,
                "dates": [],
            }
        )
    if special_cfg.get("birthdays_page", True):
        raw_pages.append(
            {
                "page_type": "special_birthdays",
                "title": "ANIVERSÁRIOS & DATAS IMPORTANTES",
                "month": None,
                "year": year if is_dated else None,
                "dates": [],
            }
        )
    if special_cfg.get("contacts_page", True):
        raw_pages.append(
            {
                "page_type": "special_contacts",
                "title": "CONTATOS IMPORTANTES",
                "month": None,
                "year": year if is_dated else None,
                "dates": [],
            }
        )

    # 2. Geração de Datas (Datada ou Permanente)
    total_days_generated = 0
    seen_iso: set[str] = set()

    if is_dated:
        try:
            start_dt = datetime.strptime(cal_cfg.get("start_date", f"{year}-01-01"), "%Y-%m-%d").date()
            end_dt = datetime.strptime(cal_cfg.get("end_date", f"{year}-12-31"), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"Formato de data inválido (esperado AAAA-MM-DD): {exc}") from exc

        if start_dt > end_dt:
            raise ValueError("A data inicial deve ser anterior ou igual à data final.")
        if (end_dt - start_dt).days > 1100:
            raise ValueError("O intervalo máximo por agenda é de 3 anos (1100 dias).")

        all_dates: list[date] = []
        cursor = start_dt
        while cursor <= end_dt:
            all_dates.append(cursor)
            cursor += timedelta(days=1)

        years_in_range = {d.year for d in all_dates}
        holiday_lookup = _build_holiday_lookup(
            years_in_range, highlight_national, state_code, custom_holidays
        )

        entries = []
        for dt in all_dates:
            entry = _make_dated_entry(dt, holiday_lookup, month_style)
            if entry["iso"] in seen_iso:
                raise ValueError(f"Data duplicada detectada: {entry['iso']}")
            seen_iso.add(entry["iso"])
            entries.append(entry)
        total_days_generated = len(entries)
    else:
        # Agenda Permanente (Não Datada): 12 meses completos (366 dias incluindo 29/02)
        days_per_month = {1: 31, 2: 29, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
        entries = []
        idx = 0
        for m in range(1, 13):
            for d_num in range(1, days_per_month[m] + 1):
                idx += 1
                entries.append(_make_undated_entry(m, d_num, month_style, idx))
        total_days_generated = len(entries)

    # 3. Agrupamento em Páginas conforme Layout
    mini_cal_cache: dict[tuple[int, int], dict[str, Any]] = {}

    def get_mini_cal(yr: int | None, mo: int | None) -> dict[str, Any] | None:
        if not cal_cfg.get("show_mini_calendar", True) or not is_dated or not yr or not mo:
            return None
        key = (yr, mo)
        if key not in mini_cal_cache:
            mini_cal_cache[key] = build_mini_calendar(yr, mo, week_starts_on)
        return mini_cal_cache[key]

    current_month_marker: tuple[int | None, int] | None = None

    def maybe_add_month_opener(yr: int | None, mo: int) -> None:
        nonlocal current_month_marker
        key = (yr, mo)
        if include_month_openers and key != current_month_marker:
            current_month_marker = key
            raw_pages.append(
                {
                    "page_type": "month_opener",
                    "title": format_month_label(mo, yr, month_style),
                    "month": mo,
                    "year": yr,
                    "dates": [],
                    "mini_calendar": get_mini_cal(yr, mo),
                }
            )
        else:
            current_month_marker = key

    if layout_mode in ("1_dpp", "financial", "corporate", "planner"):
        page_type_map = {
            "1_dpp": "daily_1dpp",
            "financial": "financial_daily",
            "corporate": "corporate_daily",
            "planner": "planner_daily",
        }
        base_pt = page_type_map[layout_mode]
        i = 0
        while i < len(entries):
            e = entries[i]
            maybe_add_month_opener(e["year"], e["month"])

            # Sábado e domingo juntos (apenas quando datada e weekend_mode == "together")
            if (
                is_dated
                and layout_mode == "1_dpp"
                and weekend_mode == "together"
                and e["weekday_num"] == 6
                and i + 1 < len(entries)
                and entries[i + 1]["weekday_num"] == 0
            ):
                e_next = entries[i + 1]
                raw_pages.append(
                    {
                        "page_type": "daily_weekend_shared",
                        "title": f"{e['day']:02d} e {e_next['day']:02d} • {e['month_label']}",
                        "month": e["month"],
                        "year": e["year"],
                        "dates": [e, e_next],
                        "mini_calendar": get_mini_cal(e["year"], e["month"]),
                    }
                )
                i += 2
            else:
                raw_pages.append(
                    {
                        "page_type": base_pt,
                        "title": f"{e['day']:02d} • {e['month_label']}",
                        "month": e["month"],
                        "year": e["year"],
                        "dates": [e],
                        "mini_calendar": get_mini_cal(e["year"], e["month"]),
                    }
                )
                i += 1

    elif layout_mode == "2_dpp":
        i = 0
        while i < len(entries):
            e1 = entries[i]
            maybe_add_month_opener(e1["year"], e1["month"])
            pair = [e1]
            if i + 1 < len(entries):
                e2 = entries[i + 1]
                # Se mudou de mês e há abertura de mês, evita cruzar meses na mesma página se opener estiver ativo
                if include_month_openers and (e2["month"] != e1["month"] or e2["year"] != e1["year"]):
                    i += 1
                else:
                    pair.append(e2)
                    i += 2
            else:
                i += 1
            raw_pages.append(
                {
                    "page_type": "daily_2dpp",
                    "title": f"{pair[0]['day']:02d}" + (f" / {pair[1]['day']:02d}" if len(pair) > 1 else "") + f" • {pair[0]['month_label']}",
                    "month": pair[0]["month"],
                    "year": pair[0]["year"],
                    "dates": pair,
                    "mini_calendar": get_mini_cal(pair[0]["year"], pair[0]["month"]),
                }
            )

    elif layout_mode == "weekly":
        if is_dated:
            current_week: list[dict[str, Any]] = []
            for e in entries:
                # Inicia nova semana quando encontra o dia de início configurado
                if current_week and e["weekday_num"] == week_starts_on:
                    first_e = current_week[0]
                    maybe_add_month_opener(first_e["year"], first_e["month"])
                    raw_pages.append(
                        {
                            "page_type": "weekly_spread",
                            "title": f"SEMANA • {first_e['day']:02d}/{first_e['month']:02d} a {current_week[-1]['day']:02d}/{current_week[-1]['month']:02d}",
                            "month": first_e["month"],
                            "year": first_e["year"],
                            "dates": current_week,
                            "mini_calendar": get_mini_cal(first_e["year"], first_e["month"]),
                        }
                    )
                    current_week = []
                current_week.append(e)
            if current_week:
                first_e = current_week[0]
                maybe_add_month_opener(first_e["year"], first_e["month"])
                raw_pages.append(
                    {
                        "page_type": "weekly_spread",
                        "title": f"SEMANA • {first_e['day']:02d}/{first_e['month']:02d} a {current_week[-1]['day']:02d}/{current_week[-1]['month']:02d}",
                        "month": first_e["month"],
                        "year": first_e["year"],
                        "dates": current_week,
                        "mini_calendar": get_mini_cal(first_e["year"], first_e["month"]),
                    }
                )
        else:
            # 53 semanas permanentes
            for w in range(1, 54):
                mo = min(12, ((w - 1) * 12) // 53 + 1)
                maybe_add_month_opener(None, mo)
                raw_pages.append(
                    {
                        "page_type": "weekly_spread",
                        "title": f"PLANEJAMENTO SEMANAL • SEMANA {w:02d}",
                        "month": mo,
                        "year": None,
                        "dates": [],
                        "extra": {"week_number": w},
                    }
                )

    elif layout_mode == "monthly":
        # Agrupado por mês: Visão Mensal + Semanas do mês + Notas/Controle
        by_month: list[tuple[tuple[int | None, int], list[dict[str, Any]]]] = []
        month_map: dict[tuple[int | None, int], list[dict[str, Any]]] = {}
        for e in entries:
            k = (e["year"], e["month"])
            if k not in month_map:
                month_map[k] = []
                by_month.append((k, month_map[k]))
            month_map[k].append(e)

        for (yr, mo), m_entries in by_month:
            maybe_add_month_opener(yr, mo)
            raw_pages.append(
                {
                    "page_type": "monthly_view",
                    "title": f"VISÃO MENSAL • {format_month_label(mo, yr, month_style)}",
                    "month": mo,
                    "year": yr,
                    "dates": m_entries,
                    "mini_calendar": build_mini_calendar(yr or year, mo, week_starts_on),
                }
            )
            # Dividir em blocos semanais dentro do mês
            chunk: list[dict[str, Any]] = []
            for e in m_entries:
                if chunk and is_dated and e["weekday_num"] == week_starts_on:
                    raw_pages.append(
                        {
                            "page_type": "weekly_spread",
                            "title": f"SEMANA • {chunk[0]['day']:02d}/{mo:02d} a {chunk[-1]['day']:02d}/{mo:02d}",
                            "month": mo,
                            "year": yr,
                            "dates": chunk,
                            "mini_calendar": get_mini_cal(yr, mo),
                        }
                    )
                    chunk = []
                elif not is_dated and len(chunk) == 7:
                    raw_pages.append(
                        {
                            "page_type": "weekly_spread",
                            "title": f"SEMANA • {format_month_label(mo, None, month_style)}",
                            "month": mo,
                            "year": None,
                            "dates": chunk,
                        }
                    )
                    chunk = []
                chunk.append(e)
            if chunk:
                raw_pages.append(
                    {
                        "page_type": "weekly_spread",
                        "title": f"SEMANA • {chunk[0]['day']:02d}/{mo:02d} a {chunk[-1]['day']:02d}/{mo:02d}",
                        "month": mo,
                        "year": yr,
                        "dates": chunk,
                        "mini_calendar": get_mini_cal(yr, mo),
                    }
                )

    # 4. Páginas finais de Notas
    notes_count = int(special_cfg.get("notes_end_pages", 2))
    for n in range(1, notes_count + 1):
        raw_pages.append(
            {
                "page_type": "special_notes",
                "title": f"ANOTAÇÕES ({n}/{notes_count})",
                "month": None,
                "year": year if is_dated else None,
                "dates": [],
            }
        )

    # 5. Pós-processamento: numeração, margens espelhadas, elementos ativos e rodapé
    total_pages = len(raw_pages)
    mirror_margins = bool(page_setup.get("mirror_margins", True))
    m_top = float(page_setup.get("margin_top_mm", 12.0))
    m_bottom = float(page_setup.get("margin_bottom_mm", 12.0))
    m_inner = float(page_setup.get("margin_inner_mm", 18.0))
    m_outer = float(page_setup.get("margin_outer_mm", 10.0))

    month_first_page: dict[int, int] = {}
    date_page_index: dict[str, int] = {}
    pages: list[dict[str, Any]] = []

    for idx, page in enumerate(raw_pages, start=1):
        is_even = idx % 2 == 0
        page["page_number"] = idx
        page["is_even"] = is_even

        if mirror_margins and is_even:
            eff_left, eff_right = m_outer, m_inner
        else:
            eff_left, eff_right = m_inner, m_outer

        page["effective_margins"] = {
            "top": m_top,
            "bottom": m_bottom,
            "left": eff_left,
            "right": eff_right,
            "inner": m_inner,
            "outer": m_outer,
        }

        if page.get("month") and page["month"] not in month_first_page:
            month_first_page[page["month"]] = idx
        for d in page.get("dates", []):
            date_page_index[d["iso"]] = idx

        # Filtrar elementos ativos e resolver variáveis
        active_els = []
        for el in elements:
            if _should_show_element(el, page, total_pages):
                resolved = dict(el)
                if resolved.get("text"):
                    resolved["resolved_text"] = _resolve_template_vars(resolved["text"], page, recipient)
                active_els.append(resolved)
        active_els.sort(key=lambda item: item.get("z_index", 10))
        page["active_elements"] = active_els

        # Rodapé e resolução de variáveis de personalização em massa
        page["show_footer"] = _should_show_footer(footer_cfg, page, total_pages)
        if recipient:
            page["recipient"] = recipient
        pages.append(page)

    return {
        "total_pages": total_pages,
        "total_sheets": (total_pages + 1) // 2,
        "total_days": total_days_generated,
        "is_dated": is_dated,
        "layout_mode": layout_mode,
        "month_first_page": month_first_page,
        "date_page_index": date_page_index,
        "pages": pages,
    }
