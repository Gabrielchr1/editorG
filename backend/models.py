"""Modelos SQLAlchemy da plataforma EditorGráfica Pro."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    """Representa um projeto independente de miolo de agenda."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    client_name = Column(String(200), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    year = Column(Integer, nullable=False, default=2026)
    template_type = Column(String(64), nullable=False, default="1_dpp")
    format_name = Column(String(64), nullable=False, default="15 x 21 cm (A5)")
    config_json = Column(Text, nullable=False)
    thumbnail_svg = Column(Text, nullable=False, default="")
    page_count = Column(Integer, nullable=False, default=0)
    is_favorite = Column(Integer, nullable=False, default=0)
    last_exported_at = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class LibraryItem(Base):
    """Biblioteca reutilizável de logotipos, frases, paletas CMYK e elementos gráficos."""

    __tablename__ = "library_items"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False, index=True)  # logo | phrase | palette | graphic | font
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    tags = Column(Text, nullable=False, default="")
    content_json = Column(Text, nullable=False, default="{}")
    file_path = Column(String(500), nullable=False, default="")
    is_system = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
