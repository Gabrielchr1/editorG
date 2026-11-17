"""Aplicação FastAPI principal da plataforma EditorGráfica Pro."""

from __future__ import annotations

import copy
import csv
import io
import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import openpyxl
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from sqlalchemy.orm import Session

from backend.calendar_engine import STATE_HOLIDAYS_BR, generate_agenda_pages
from backend.database import SessionLocal, get_db, run_migrations
from backend.models import LibraryItem, Project
from backend.pdf_engine import (
    export_batch_personalized_zip,
    export_project_bundle,
    get_available_fonts,
    render_pages_to_pdf_bytes,
)
from backend.preflight_engine import run_preflight
from backend.schemas import (
    BatchExportRequest,
    ExportRequest,
    LibraryItemCreate,
    ProjectConfig,
    ProjectCreate,
    ProjectDuplicateRequest,
    ProjectUpdate,
    cmyk_to_hex,
    hex_to_cmyk,
)
from backend.seed_data import (
    CMYK_PALETTES,
    MONTHLY_MOTIVATIONAL_PHRASES,
    PHRASE_PACKS,
    build_config_from_template,
    get_template_catalog,
    seed_initial_data,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = BASE_DIR / "uploads"
ALLOWED_UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".pdf"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    run_migrations()
    db = SessionLocal()
    try:
        seed_initial_data(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="EditorGráfica Pro - Plataforma de Miolos de Agendas",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _serialize_project(proj: Project, include_config: bool = True) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": proj.id,
        "name": proj.name,
        "client_name": proj.client_name,
        "description": proj.description,
        "year": proj.year,
        "template_type": proj.template_type,
        "format_name": proj.format_name,
        "page_count": proj.page_count,
        "is_favorite": proj.is_favorite,
        "last_exported_at": proj.last_exported_at,
        "created_at": proj.created_at.isoformat() if proj.created_at else None,
        "updated_at": proj.updated_at.isoformat() if proj.updated_at else None,
    }
    if include_config:
        try:
            data["config"] = json.loads(proj.config_json)
        except Exception:
            data["config"] = {}
    return data


def _validate_and_normalize_config(raw_cfg: dict[str, Any]) -> dict[str, Any]:
    validated = ProjectConfig.model_validate(raw_cfg)
    return validated.model_dump()


def _format_name_from_config(cfg: dict[str, Any]) -> str:
    ps = cfg.get("page_setup", {})
    w_cm = float(ps.get("width_mm", 150.0)) / 10.0
    h_cm = float(ps.get("height_mm", 210.0)) / 10.0
    tag = " (A5)" if abs(w_cm - 15.0) < 0.2 and abs(h_cm - 21.0) < 0.2 else ""
    return f"{w_cm:g} x {h_cm:g} cm{tag}"


@app.get("/api/health")
def health_check():
    return {"status": "ok", "fonts": get_available_fonts()}


@app.get("/api/meta")
def get_platform_metadata():
    """Retorna fontes, paletas CMYK, modelos, pacotes de frases e feriados estaduais."""
    return {
        "fonts": get_available_fonts(),
        "palettes": CMYK_PALETTES,
        "templates": get_template_catalog(),
        "monthly_phrases": MONTHLY_MOTIVATIONAL_PHRASES,
        "phrase_packs": PHRASE_PACKS,
        "state_holidays": STATE_HOLIDAYS_BR,
    }


@app.get("/api/color/cmyk-to-hex")
def api_cmyk_to_hex(c: int = 0, m: int = 0, y: int = 0, k: int = 100):
    return {"c": c, "m": m, "y": y, "k": k, "hex": cmyk_to_hex(c, m, y, k)}


@app.get("/api/color/hex-to-cmyk")
def api_hex_to_cmyk(hex_color: str = "#000000"):
    c, m, y, k = hex_to_cmyk(hex_color)
    return {"c": c, "m": m, "y": y, "k": k, "hex": cmyk_to_hex(c, m, y, k)}


# ---------------- PROJETOS ----------------


@app.get("/api/projects")
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.updated_at.desc(), Project.id.desc()).all()
    items = []
    for p in projects:
        d = _serialize_project(p, include_config=True)
        cfg = d.get("config", {})
        d["summary"] = {
            "is_dated": cfg.get("calendar", {}).get("is_dated", True),
            "layout_mode": cfg.get("calendar", {}).get("layout_mode", "1_dpp"),
            "palette_name": cfg.get("colors", {}).get("palette_name", "Personalizada"),
            "ruling_type": cfg.get("ruling", {}).get("ruling_type", "horizontal"),
            "bleed_mm": cfg.get("page_setup", {}).get("bleed_mm", 3.0),
        }
        items.append(d)
    return {"projects": items}


@app.post("/api/projects", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    raw_cfg = payload.config if payload.config else build_config_from_template(payload.template_id)
    cfg = _validate_and_normalize_config(raw_cfg)
    gen = generate_agenda_pages(cfg)

    proj = Project(
        name=payload.name.strip(),
        client_name=payload.client_name.strip(),
        description=payload.description.strip(),
        year=int(cfg["calendar"]["year"]),
        template_type=payload.template_id or cfg["calendar"]["layout_mode"],
        format_name=_format_name_from_config(cfg),
        config_json=json.dumps(cfg, ensure_ascii=False),
        page_count=gen["total_pages"],
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return _serialize_project(proj)


@app.get("/api/projects/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    return _serialize_project(proj)


@app.put("/api/projects/{project_id}")
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")

    if payload.name is not None:
        proj.name = payload.name.strip()
    if payload.client_name is not None:
        proj.client_name = payload.client_name.strip()
    if payload.description is not None:
        proj.description = payload.description.strip()
    if payload.is_favorite is not None:
        proj.is_favorite = int(payload.is_favorite)

    if payload.config is not None:
        try:
            cfg = _validate_and_normalize_config(payload.config)
            gen = generate_agenda_pages(cfg)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        proj.config_json = json.dumps(cfg, ensure_ascii=False)
        proj.year = int(cfg["calendar"]["year"])
        proj.template_type = cfg["calendar"]["layout_mode"]
        proj.format_name = _format_name_from_config(cfg)
        proj.page_count = gen["total_pages"]

    db.commit()
    db.refresh(proj)
    return _serialize_project(proj)


@app.post("/api/projects/{project_id}/duplicate", status_code=201)
def duplicate_project(
    project_id: int,
    payload: ProjectDuplicateRequest | None = None,
    db: Session = Depends(get_db),
):
    orig = db.query(Project).filter(Project.id == project_id).first()
    if not orig:
        raise HTTPException(status_code=404, detail="Projeto original não encontrado.")

    new_name = (payload.new_name.strip() if payload and payload.new_name else None) or f"{orig.name} (Cópia)"
    new_client = (payload.new_client_name.strip() if payload and payload.new_client_name else orig.client_name)
    dup = Project(
        name=new_name,
        client_name=new_client,
        description=orig.description,
        year=orig.year,
        template_type=orig.template_type,
        format_name=orig.format_name,
        config_json=orig.config_json,
        page_count=orig.page_count,
        is_favorite=0,
    )
    db.add(dup)
    db.commit()
    db.refresh(dup)
    return _serialize_project(dup)


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    db.delete(proj)
    db.commit()
    return {"deleted": True, "id": project_id}


# ---------------- MOTOR DE CALENDÁRIO & CONFERÊNCIA ----------------


@app.post("/api/calendar/preview")
def preview_calendar_from_config(config: dict[str, Any]):
    """Gera estrutura paginada em tempo real a partir de uma configuração JSON."""
    try:
        cfg = _validate_and_normalize_config(config)
        return generate_agenda_pages(cfg)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/preview-pages")
def preview_project_pages(
    project_id: int,
    config_override: dict[str, Any] | None = None,
    db: Session = Depends(get_db),
):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    raw = config_override if config_override else json.loads(proj.config_json)
    try:
        cfg = _validate_and_normalize_config(raw)
        return generate_agenda_pages(cfg)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------- PRÉ-IMPRESSÃO & EXPORTAÇÃO ----------------


@app.post("/api/projects/{project_id}/preflight")
def project_preflight(
    project_id: int,
    config_override: dict[str, Any] | None = None,
    db: Session = Depends(get_db),
):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    raw = config_override if config_override else json.loads(proj.config_json)
    cfg = _validate_and_normalize_config(raw)
    return run_preflight(cfg)


@app.post("/api/projects/{project_id}/export")
def export_project(project_id: int, req: ExportRequest, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    raw = req.config_override if req.config_override else json.loads(proj.config_json)
    try:
        cfg = _validate_and_normalize_config(raw)
        data, media_type, filename = export_project_bundle(
            config=cfg,
            export_mode=req.export_mode,
            include_bleed=req.include_bleed,
            include_crop_marks=req.include_crop_marks,
            mirror_margins=req.mirror_margins,
            page_range=req.page_range,
            project_name=proj.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    proj.last_exported_at = datetime.now(timezone.utc).isoformat()
    db.commit()

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/projects/{project_id}/preview-pdf")
def preview_single_page_pdf(
    project_id: int,
    page_number: int = Query(1, ge=1),
    include_bleed: bool = Query(True),
    include_crop_marks: bool = Query(True),
    mirror_margins: bool = Query(True),
    config_override: dict[str, Any] | None = None,
    db: Session = Depends(get_db),
):
    """Renderiza PDF real fiel da página especificada para conferência no navegador."""
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    raw = config_override if config_override else json.loads(proj.config_json)
    cfg = _validate_and_normalize_config(raw)
    cfg_copy = copy.deepcopy(cfg)
    cfg_copy["page_setup"]["mirror_margins"] = mirror_margins

    gen = generate_agenda_pages(cfg_copy)
    pages = gen["pages"]
    if not pages:
        raise HTTPException(status_code=400, detail="Nenhuma página gerada.")
    idx = min(max(0, page_number - 1), len(pages) - 1)
    pdf_bytes = render_pages_to_pdf_bytes(
        cfg_copy,
        [pages[idx]],
        include_bleed=include_bleed,
        include_crop_marks=include_crop_marks,
        mirror_margins=mirror_margins,
        title=f"{proj.name} - Página {idx + 1}",
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="preview_p{idx + 1}.pdf"'},
    )


@app.post("/api/projects/{project_id}/batch-export")
def batch_export_project(project_id: int, req: BatchExportRequest, db: Session = Depends(get_db)):
    """Personalização em massa: gera ZIP com um PDF personalizado para cada nome/empresa."""
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Projeto não encontrado.")
    raw = req.config_override if req.config_override else json.loads(proj.config_json)
    cfg = _validate_and_normalize_config(raw)
    recipients = [r.model_dump() for r in req.recipients]
    zip_bytes = export_batch_personalized_zip(
        config=cfg,
        recipients=recipients,
        include_bleed=req.include_bleed,
        include_crop_marks=req.include_crop_marks,
        mirror_margins=req.mirror_margins,
        page_range=req.page_range,
        project_name=proj.name,
    )
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", proj.name).strip("_") or "Agenda"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_lote_{len(recipients)}.zip"'},
    )


@app.post("/api/batch/parse-recipients")
async def parse_batch_recipients_file(file: UploadFile = File(...)):
    """Importa lista de destinatários para personalização em massa a partir de CSV ou XLSX."""
    ext = Path(file.filename or "").suffix.lower()
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Arquivo de lista excede 5 MB.")

    recipients: list[dict[str, str]] = []
    if ext == ".csv":
        text = content.decode("utf-8-sig", errors="replace")
        dialect = csv.Sniffer().sniff(text[:1024], delimiters=",;\t") if len(text) > 10 else csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        for row in reader:
            norm = {str(k or "").strip().lower(): str(v or "").strip() for k, v in row.items()}
            nome = norm.get("nome") or norm.get("name") or next(iter(norm.values()), "")
            if nome:
                recipients.append(
                    {
                        "nome": nome,
                        "empresa": norm.get("empresa") or norm.get("company") or "",
                        "cargo": norm.get("cargo") or norm.get("role") or "",
                        "extra": norm.get("extra") or "",
                    }
                )
    elif ext in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if rows:
            headers = [str(c or "").strip().lower() for c in rows[0]]
            for r in rows[1:]:
                row_map = {headers[i]: str(r[i] or "").strip() for i in range(min(len(headers), len(r)))}
                nome = row_map.get("nome") or row_map.get("name") or (str(r[0] or "").strip() if r else "")
                if nome:
                    recipients.append(
                        {
                            "nome": nome,
                            "empresa": row_map.get("empresa") or row_map.get("company") or "",
                            "cargo": row_map.get("cargo") or row_map.get("role") or "",
                            "extra": row_map.get("extra") or "",
                        }
                    )
    else:
        raise HTTPException(status_code=400, detail="Envie um arquivo .csv ou .xlsx.")

    return {"count": len(recipients), "recipients": recipients[:500]}


# ---------------- UPLOAD SEGURO & BIBLIOTECA ----------------


@app.post("/api/upload")
async def upload_graphic_asset(
    file: UploadFile = File(...),
    save_to_library: bool = Query(True),
    category: str = Query("logo"),
    db: Session = Depends(get_db),
):
    """Recebe PNG, JPG, SVG ou PDF com validação de conteúdo e segurança."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    orig_name = Path(file.filename or "arquivo").name
    ext = Path(orig_name).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Formato não suportado. Envie PNG, JPG, SVG ou PDF.",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo excede o limite de 15 MB.")

    width_px, height_px = None, None
    notes = ""

    if ext in (".png", ".jpg", ".jpeg"):
        try:
            with Image.open(io.BytesIO(raw)) as im:
                im.verify()
            with Image.open(io.BytesIO(raw)) as im2:
                width_px, height_px = im2.size
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Imagem corrompida ou inválida: {exc}") from exc
    elif ext == ".svg":
        txt = raw.decode("utf-8", errors="ignore")
        if "<svg" not in txt.lower():
            raise HTTPException(status_code=400, detail="Arquivo SVG inválido.")
        # Remove tags <script> por segurança XSS
        cleaned = re.sub(r"<script[\s\S]*?</script>", "", txt, flags=re.IGNORECASE)
        raw = cleaned.encode("utf-8")
        notes = "Gráfico vetorial SVG sanitizado."
    elif ext == ".pdf":
        if not raw.lstrip().startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Arquivo PDF inválido.")
        notes = "PDF validado. Para melhor renderização em logotipo inline, recomenda-se SVG ou PNG 300 DPI."

    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(orig_name).stem).strip("_") or "asset"
    stored_name = f"{safe_stem}_{uuid4().hex[:8]}{ext}"
    dest = UPLOADS_DIR / stored_name
    dest.write_bytes(raw)
    url = f"/uploads/{stored_name}"

    lib_item = None
    if save_to_library:
        lib_cat = category if category in ("logo", "graphic") else "logo"
        item = LibraryItem(
            category=lib_cat,
            name=orig_name,
            description=notes or f"Arquivo {ext.upper().lstrip('.')} ({width_px or 'vetor'}x{height_px or 'vetor'})",
            tags=f"upload,{ext.lstrip('.')}",
            content_json=json.dumps({"url": url, "width_px": width_px, "height_px": height_px, "ext": ext}),
            file_path=url,
            is_system=0,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        lib_item = {"id": item.id, "name": item.name, "url": url}

    return {
        "url": url,
        "filename": orig_name,
        "ext": ext,
        "width_px": width_px,
        "height_px": height_px,
        "notes": notes,
        "library_item": lib_item,
    }


@app.get("/api/library")
def list_library(category: str | None = None, db: Session = Depends(get_db)):
    q = db.query(LibraryItem)
    if category:
        q = q.filter(LibraryItem.category == category)
    items = q.order_by(LibraryItem.is_system.asc(), LibraryItem.id.desc()).all()
    out = []
    for it in items:
        try:
            content = json.loads(it.content_json)
        except Exception:
            content = {}
        out.append(
            {
                "id": it.id,
                "category": it.category,
                "name": it.name,
                "description": it.description,
                "tags": it.tags,
                "content": content,
                "file_path": it.file_path,
                "is_system": bool(it.is_system),
            }
        )
    return {"items": out}


@app.post("/api/library", status_code=201)
def create_library_item(payload: LibraryItemCreate, db: Session = Depends(get_db)):
    item = LibraryItem(
        category=payload.category,
        name=payload.name.strip(),
        description=payload.description.strip(),
        tags=payload.tags.strip(),
        content_json=json.dumps(payload.content_json, ensure_ascii=False),
        file_path=payload.file_path.strip(),
        is_system=0,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "category": item.category,
        "name": item.name,
        "description": item.description,
        "content": payload.content_json,
        "file_path": item.file_path,
        "is_system": False,
    }


@app.delete("/api/library/{item_id}")
def delete_library_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(LibraryItem).filter(LibraryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item da biblioteca não encontrado.")
    db.delete(item)
    db.commit()
    return {"deleted": True, "id": item_id}


# ---------------- ARQUIVOS ESTÁTICOS & SPA ----------------

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_spa():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return {"message": "Interface em construção."}
    return FileResponse(str(index_path))
