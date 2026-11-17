"""Suíte de testes automatizados da plataforma EditorGráfica Pro."""

from __future__ import annotations

import base64
import io
import json
import re
import zipfile
import zlib
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from PIL import Image
from reportlab.lib.units import mm
from sqlalchemy import create_engine, text

from backend.calendar_engine import compute_easter, generate_agenda_pages, get_national_holidays_for_year
from backend.database import SessionLocal, ensure_columns, run_migrations
from backend.pdf_engine import export_batch_personalized_zip, export_project_bundle
from backend.preflight_engine import run_preflight
from backend.schemas import default_project_config, make_cmyk
from backend.seed_data import seed_initial_data
from main import app


def _extract_pdf_streams_text(pdf_bytes: bytes) -> bytes:
    """Descomprime todos os streams Flate/ASCII85 de um PDF ReportLab para inspeção de operadores."""
    chunks = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf_bytes, flags=re.DOTALL):
        raw = m.group(1).strip()
        try:
            if raw.endswith(b"~>"):
                raw = base64.a85decode(raw, adobe=True)
            chunks.append(zlib.decompress(raw))
        except Exception:
            chunks.append(raw)
    return b"\n".join(chunks)


def test_sqlite_non_destructive_migration(tmp_path: Path):
    db_file = tmp_path / "test_mig.db"
    eng = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    applied = run_migrations(eng)
    assert 1 in applied and 2 in applied

    # Insere um registro real
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO projects (name, client_name, description, year, template_type, format_name, config_json, thumbnail_svg, page_count, is_favorite, created_at, updated_at) "
                "VALUES ('Proj Teste', 'Cliente A', '', 2026, '1_dpp', '15x21', '{}', '', 10, 0, '2026-01-01', '2026-01-01')"
            )
        )
        # Simula evolução futura de esquema sem resetar dados
        ensure_columns(conn, "projects", {"nova_coluna_futura": "TEXT DEFAULT 'ok'"})
        row = conn.execute(text("SELECT name, nova_coluna_futura FROM projects WHERE name='Proj Teste'")).fetchone()
        assert row == ("Proj Teste", "ok")


def test_calendar_2026_and_leap_2028_exact_dates():
    for year, expected_days in [(2026, 365), (2028, 366)]:
        cfg = default_project_config()
        cfg["calendar"]["year"] = year
        cfg["calendar"]["start_date"] = f"{year}-01-01"
        cfg["calendar"]["end_date"] = f"{year}-12-31"
        cfg["calendar"]["weekend_mode"] = "separate"
        cfg["calendar"]["include_month_openers"] = False
        res = generate_agenda_pages(cfg)
        assert res["total_days"] == expected_days

        collected_dates = []
        for p in res["pages"]:
            for d in p.get("dates", []):
                collected_dates.append(d["iso"])
                dt = date.fromisoformat(d["iso"])
                expected_sun0 = (dt.weekday() + 1) % 7
                assert d["weekday_num"] == expected_sun0

        assert len(collected_dates) == expected_days
        assert len(set(collected_dates)) == expected_days
        assert collected_dates[0] == f"{year}-01-01"
        assert collected_dates[-1] == f"{year}-12-31"


def test_calendar_weekend_together_vs_separate_and_undated():
    cfg = default_project_config()
    cfg["calendar"]["weekend_mode"] = "together"
    res_together = generate_agenda_pages(cfg)
    cfg["calendar"]["weekend_mode"] = "separate"
    res_sep = generate_agenda_pages(cfg)
    assert res_together["total_pages"] < res_sep["total_pages"]

    # Agenda permanente (não datada): 366 dias incluindo 29/02
    cfg_perm = default_project_config()
    cfg_perm["calendar"]["is_dated"] = False
    res_perm = generate_agenda_pages(cfg_perm)
    assert res_perm["total_days"] == 366
    assert not res_perm["is_dated"]


def test_holidays_easter_and_custom():
    assert compute_easter(2026) == date(2026, 4, 5)
    nat = get_national_holidays_for_year(2026)
    assert "2026-02-17" in nat  # Carnaval Terça
    assert "2026-04-03" in nat  # Sexta-feira Santa
    assert "2026-06-04" in nat  # Corpus Christi
    assert "2026-11-20" in nat  # Consciência Negra

    cfg = default_project_config()
    cfg["calendar"]["state_code"] = "SP"
    cfg["calendar"]["custom_holidays"] = [
        {"id": "c1", "date": "03-08", "name": "Dia da Mulher", "type": "commemorative", "recurring": True}
    ]
    res = generate_agenda_pages(cfg)
    sp_page = res["pages"][res["date_page_index"]["2026-07-09"] - 1]
    assert any("Revolução" in h["name"] for h in sp_page["dates"][0]["holidays"])
    wom_page = res["pages"][res["date_page_index"]["2026-03-08"] - 1]
    assert any("Dia da Mulher" in h["name"] for d in wom_page["dates"] for h in d["holidays"])


def test_element_targeting_and_preflight():
    cfg = default_project_config()
    cfg["elements"] = [
        {
            "id": "el_safe",
            "type": "phrase",
            "label": "Frase Segura",
            "text": "Texto de Janeiro",
            "x_mm": 25.0,
            "y_mm": 150.0,
            "width_mm": 100.0,
            "height_mm": 14.0,
            "rotation_deg": 0.0,
            "color": make_cmyk(0, 0, 0, 100),
            "target_rule": "month_openers",
            "target_months": [1],
        },
        {
            "id": "el_unsafe",
            "type": "phrase",
            "label": "Frase na Borda",
            "text": "Fora da segurança",
            "x_mm": 1.0,
            "y_mm": 1.0,
            "width_mm": 60.0,
            "height_mm": 12.0,
            "rotation_deg": 0.0,
            "color": make_cmyk(0, 0, 0, 100),
            "target_rule": "all",
        },
    ]
    res = generate_agenda_pages(cfg)
    jan_opener = next(p for p in res["pages"] if p["page_type"] == "month_opener" and p["month"] == 1)
    feb_opener = next(p for p in res["pages"] if p["page_type"] == "month_opener" and p["month"] == 2)
    assert any(e["id"] == "el_safe" for e in jan_opener["active_elements"])
    assert not any(e["id"] == "el_safe" for e in feb_opener["active_elements"])

    pf = run_preflight(cfg)
    assert pf["status"] == "warning"
    assert len(pf["out_of_safety"]) == 1
    assert pf["out_of_safety"][0]["id"] == "el_unsafe"


def test_pdf_cmyk_dimensions_crop_marks_and_full_365_days():
    cfg = default_project_config()
    cfg["calendar"]["weekend_mode"] = "separate"
    cfg["footer"]["company_name"] = "Gráfica Central CMYK"

    # 1. PDF completo sem sangria e sem marcas de corte -> exatamente 150 x 210 mm
    pdf_exact, mime, _ = export_project_bundle(
        cfg,
        export_mode="single_pdf",
        include_bleed=False,
        include_crop_marks=False,
        mirror_margins=True,
        page_range="1-10",
        project_name="TesteExato",
    )
    assert mime == "application/pdf"
    assert pdf_exact.startswith(b"%PDF-")
    decoded_stream = _extract_pdf_streams_text(pdf_exact)
    assert b" k\n" in decoded_stream or b" K\n" in decoded_stream
    assert b" rg\n" not in decoded_stream and b" RG\n" not in decoded_stream

    # Verifica MediaBox no PDF gerado (150mm x 210mm em pontos)
    expected_w_pt = 150.0 * mm
    expected_h_pt = 210.0 * mm
    mb_match = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)\s*\]", pdf_exact)
    assert mb_match is not None
    assert abs(float(mb_match.group(1)) - expected_w_pt) < 0.5
    assert abs(float(mb_match.group(2)) - expected_h_pt) < 0.5

    # 2. PDF completo de 365+ dias com sangria 3mm + marcas de corte
    pdf_full, _, _ = export_project_bundle(
        cfg,
        export_mode="single_pdf",
        include_bleed=True,
        include_crop_marks=True,
        mirror_margins=True,
        project_name="Agenda365",
    )
    assert pdf_full.startswith(b"%PDF-")
    assert len(pdf_full) > 200_000

    # 3. Exportação separada por mês (.zip)
    zip_month, mime_m, _ = export_project_bundle(
        cfg, export_mode="by_month", include_bleed=True, include_crop_marks=False, project_name="PorMes"
    )
    assert mime_m == "application/zip"
    with zipfile.ZipFile(io.BytesIO(zip_month), "r") as zf:
        names = zf.namelist()
        assert "01_Janeiro.pdf" in names
        assert "12_Dezembro.pdf" in names

    # 4. Exportação páginas individuais (.zip)
    zip_ind, mime_i, _ = export_project_bundle(
        cfg, export_mode="individual_pages", include_bleed=False, include_crop_marks=False, page_range="1-3", project_name="Ind"
    )
    assert mime_i == "application/zip"
    with zipfile.ZipFile(io.BytesIO(zip_ind), "r") as zf:
        assert sorted(zf.namelist()) == ["Pagina_0001.pdf", "Pagina_0002.pdf", "Pagina_0003.pdf"]

    # 5. Personalização em massa (lote)
    batch_zip = export_batch_personalized_zip(
        cfg,
        recipients=[{"nome": "Dr. João", "empresa": "Clínica A"}, {"nome": "Dra. Maria", "empresa": "Clínica B"}],
        page_range="1-4",
        project_name="LoteTeste",
    )
    with zipfile.ZipFile(io.BytesIO(batch_zip), "r") as zf:
        assert len(zf.namelist()) == 2


@pytest.mark.asyncio
async def test_api_crud_upload_library_and_export():
    run_migrations()
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Lista inicial (contém seed)
        r_list = await client.get("/api/projects")
        assert r_list.status_code == 200
        assert len(r_list.json()["projects"]) >= 1

        # Cria novo projeto a partir do modelo financeiro
        r_create = await client.post(
            "/api/projects",
            json={"name": "Projeto API Teste", "client_name": "Empresa XYZ", "template_id": "financeiro"},
        )
        assert r_create.status_code == 201
        proj = r_create.json()
        pid = proj["id"]
        assert proj["config"]["calendar"]["layout_mode"] == "financial"

        # Upload PNG válido
        img_buf = io.BytesIO()
        Image.new("RGBA", (300, 120), (30, 80, 160, 255)).save(img_buf, format="PNG")
        img_buf.seek(0)
        r_up = await client.post(
            "/api/upload?save_to_library=true&category=logo",
            files={"file": ("logo_teste.png", img_buf, "image/png")},
        )
        assert r_up.status_code == 200
        up_data = r_up.json()
        assert up_data["width_px"] == 300

        # Rejeita extensão inválida
        r_bad = await client.post(
            "/api/upload",
            files={"file": ("malware.exe", b"MZ123", "application/octet-stream")},
        )
        assert r_bad.status_code == 400

        # Atualiza projeto com o logo enviado
        cfg = proj["config"]
        cfg["footer"]["logo_url"] = up_data["url"]
        r_upd = await client.put(f"/api/projects/{pid}", json={"config": cfg})
        assert r_upd.status_code == 200

        # Preflight
        r_pf = await client.post(f"/api/projects/{pid}/preflight")
        assert r_pf.status_code == 200
        assert r_pf.json()["total_pages"] > 300

        # Preview PDF de página única
        r_prev = await client.post(f"/api/projects/{pid}/preview-pdf?page_number=1")
        assert r_prev.status_code == 200
        assert r_prev.content.startswith(b"%PDF-")

        # Duplicação
        r_dup = await client.post(f"/api/projects/{pid}/duplicate", json={"new_name": "Cópia API"})
        assert r_dup.status_code == 201
        dup_id = r_dup.json()["id"]

        # Exportação via endpoint
        r_exp = await client.post(
            f"/api/projects/{pid}/export",
            json={"export_mode": "single_pdf", "include_bleed": True, "include_crop_marks": True, "page_range": "1-5"},
        )
        assert r_exp.status_code == 200
        assert r_exp.content.startswith(b"%PDF-")

        # Limpeza dos projetos e arquivos de teste
        assert (await client.delete(f"/api/projects/{pid}")).status_code == 200
        assert (await client.delete(f"/api/projects/{dup_id}")).status_code == 200
        if up_data.get("library_item"):
            assert (await client.delete(f"/api/library/{up_data['library_item']['id']}")).status_code == 200
        uploaded_file = Path("uploads") / Path(up_data["url"]).name
        uploaded_file.unlink(missing_ok=True)
