"""Consultas de solo lectura para el servidor MCP.

Se leen solo las columnas necesarias y se agregan en Python: así funciona igual
en SQLite (local) y Postgres (Render), sin funciones SQL específicas de un motor.
"""
from datetime import datetime, timezone

from sqlalchemy import func, select

from .db import engine, leads


def _a_utc(dt: datetime) -> datetime:
    """SQLite devuelve datetimes sin zona (se guardan en UTC); Postgres con zona."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def total_reservas() -> int:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(leads)).scalar_one()


def personas_por_dia() -> dict:
    """{date: total de personas reservadas ese día}"""
    with engine.connect() as conn:
        rows = conn.execute(
            select(leads.c.dia, func.sum(leads.c.personas)).group_by(leads.c.dia)
        ).all()
    return {r[0]: int(r[1] or 0) for r in rows}


def fechas_creacion() -> list[datetime]:
    """Fechas de creación de todas las reservas, normalizadas a UTC."""
    with engine.connect() as conn:
        rows = conn.execute(select(leads.c.creado)).all()
    return [_a_utc(r[0]) for r in rows if r[0] is not None]


def reservas_desde(desde: datetime) -> int:
    desde = _a_utc(desde)
    return sum(1 for c in fechas_creacion() if c >= desde)


def tamano_promedio_grupo() -> float | None:
    with engine.connect() as conn:
        prom = conn.execute(select(func.avg(leads.c.personas))).scalar_one()
    return round(float(prom), 2) if prom is not None else None
