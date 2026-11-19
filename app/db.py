"""Capa de datos compartida por la landing y el servidor MCP.

- En Render usa Postgres a través de la variable de entorno DATABASE_URL.
- En local, si DATABASE_URL no existe, usa un archivo SQLite (leads.db).
"""
import os
from datetime import date, datetime, timezone

from sqlalchemy import (Column, Date, DateTime, Integer, MetaData, String, Table,
                        create_engine, func, select)

from . import config

_url = os.getenv("DATABASE_URL", "sqlite:///leads.db")
# Algunos proveedores entregan "postgres://..."; SQLAlchemy necesita "postgresql+psycopg://..."
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql+psycopg://", 1)
elif _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(_url, pool_pre_ping=True)
metadata = MetaData()

leads = Table(
    "leads", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("nombre", String(80), nullable=False),
    Column("whatsapp", String(20), nullable=False),
    Column("personas", Integer, nullable=False),
    Column("dia", Date, nullable=False, index=True),
    Column("creado", DateTime(timezone=True), nullable=False),
)


def init_db() -> None:
    metadata.create_all(engine)


class SinCupo(Exception):
    pass


def ocupadas_por_dia() -> dict[date, int]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(leads.c.dia, func.count()).group_by(leads.c.dia)
        ).all()
    return {r[0]: r[1] for r in rows}


def cupos_por_dia() -> list[dict]:
    """Lista de días de campaña con mesas ocupadas y libres."""
    ocupadas = ocupadas_por_dia()
    out = []
    for d in config.DIAS_CAMPANA:
        usadas = ocupadas.get(d, 0)
        out.append({
            "dia": d.isoformat(),
            "dia_texto": config.fecha_bonita(d),
            "mesas_totales": config.MESAS_POR_DIA,
            "ocupadas": usadas,
            "libres": max(config.MESAS_POR_DIA - usadas, 0),
        })
    return out


def crear_lead(nombre: str, whatsapp: str, personas: int, dia: date) -> int:
    """Guarda una reserva. Lanza SinCupo si el día ya está lleno."""
    with engine.begin() as conn:
        usadas = conn.execute(
            select(func.count()).select_from(leads).where(leads.c.dia == dia)
        ).scalar_one()
        if usadas >= config.MESAS_POR_DIA:
            raise SinCupo(config.fecha_bonita(dia))
        res = conn.execute(leads.insert().values(
            nombre=nombre, whatsapp=whatsapp, personas=personas, dia=dia,
            creado=datetime.now(timezone.utc),
        ))
        return res.inserted_primary_key[0]


def obtener_leads(dia: date | None = None, limite: int = 50) -> list[dict]:
    q = select(leads).order_by(leads.c.creado.desc()).limit(limite)
    if dia:
        q = q.where(leads.c.dia == dia)
    with engine.connect() as conn:
        rows = conn.execute(q).mappings().all()
    return [dict(r) for r in rows]
