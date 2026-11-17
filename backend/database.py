"""Configuração do banco de dados SQLite e sistema de migração incremental."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "editor_grafica.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db():
    """Fornece uma sessão de banco de dados por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_existing_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def ensure_columns(conn, table_name: str, columns: dict[str, str]) -> None:
    """Adiciona colunas ausentes em tabelas existentes sem resetar dados."""
    existing = _get_existing_columns(conn, table_name)
    if not existing:
        return
    for col_name, col_ddl in columns.items():
        if col_name not in existing:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_ddl}"))


def _migration_v1_initial_schema(conn) -> None:
    """Garante colunas básicas iniciais para projetos e biblioteca."""
    ensure_columns(
        conn,
        "projects",
        {
            "description": "TEXT DEFAULT ''",
            "thumbnail_svg": "TEXT DEFAULT ''",
            "page_count": "INTEGER DEFAULT 0",
        },
    )
    ensure_columns(
        conn,
        "library_items",
        {
            "description": "TEXT DEFAULT ''",
            "tags": "TEXT DEFAULT ''",
        },
    )


def _migration_v2_metadata_and_export_tracking(conn) -> None:
    """Adiciona suporte a metadados de exportação e marcação de favoritos sem resetar dados."""
    ensure_columns(
        conn,
        "projects",
        {
            "is_favorite": "INTEGER DEFAULT 0",
            "last_exported_at": "TEXT DEFAULT NULL",
        },
    )
    ensure_columns(
        conn,
        "library_items",
        {
            "is_system": "INTEGER DEFAULT 0",
        },
    )


def _migration_v3_ecommerce_expansion(conn) -> None:
    """Expande tabela projects com vínculos comerciais, versão e dono sem apagar dados."""
    ensure_columns(
        conn,
        "projects",
        {
            "owner_id": "INTEGER DEFAULT NULL",
            "product_id": "INTEGER DEFAULT NULL",
            "template_id": "INTEGER DEFAULT NULL",
            "template_version": "INTEGER DEFAULT 1",
            "version": "INTEGER DEFAULT 1",
            "status": "TEXT DEFAULT 'draft'",
            "customization_options_json": "TEXT DEFAULT '{}'",
        },
    )


MIGRATIONS: list[tuple[int, str, Callable]] = [
    (1, "initial_schema_columns", _migration_v1_initial_schema),
    (2, "metadata_and_export_tracking", _migration_v2_metadata_and_export_tracking),
    (3, "ecommerce_expansion", _migration_v3_ecommerce_expansion),
]


def run_migrations(target_engine=None) -> list[int]:
    """Executa criação de tabelas e aplica migrações pendentes de forma idempotente."""
    eng = target_engine or engine
    # Importar models para registrar metadados antes de create_all
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=eng)
    applied_now: list[int] = []

    with eng.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
        )
        rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
        applied_versions = {row[0] for row in rows}

        for version, name, fn in MIGRATIONS:
            if version not in applied_versions:
                fn(conn)
                conn.execute(
                    text(
                        "INSERT INTO schema_migrations (version, name, applied_at) "
                        "VALUES (:version, :name, :applied_at)"
                    ),
                    {
                        "version": version,
                        "name": name,
                        "applied_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                applied_now.append(version)

    return applied_now
