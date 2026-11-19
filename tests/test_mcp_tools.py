"""Pruebas de las herramientas MCP con una base SQLite temporal.

DATABASE_URL se fija ANTES de importar la app, porque app.db crea el engine al importarse.
"""
import asyncio
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="fogon_test_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ.pop("LANDING_URL", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastmcp import Client  # noqa: E402

from app import config, db, mcp_server  # noqa: E402
from app.mcp_server import mcp  # noqa: E402

HOY_FIJO = date(2026, 11, 20)  # antes de la campaña: todos los días son futuros


def llamar(nombre: str, args: dict | None = None):
    async def _run():
        async with Client(mcp) as c:
            r = await c.call_tool(nombre, args or {}, raise_on_error=True)
            return r.structured_content
    return asyncio.run(_run())


@pytest.fixture(scope="module", autouse=True)
def datos():
    db.init_db()
    d1, d2 = config.DIAS_CAMPANA[0], config.DIAS_CAMPANA[1]
    db.crear_lead("María Fernanda Rojas", "+50688880001", 2, d1)
    db.crear_lead("José Mora", "+50688880002", 4, d1)
    db.crear_lead("Ana Vargas Solano", "+50688881234", 3, d2)
    yield


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(mcp_server, "_hoy", lambda: HOY_FIJO)


def test_lista_de_herramientas():
    async def _run():
        async with Client(mcp) as c:
            return await c.list_tools()
    tools = {t.name: t for t in asyncio.run(_run())}
    assert set(tools) == {"estado_campana", "cupos_por_dia", "dias_vacios", "listar_leads",
                          "resumen_campana", "datos_para_publicacion"}
    assert all(t.annotations and t.annotations.readOnlyHint for t in tools.values())


def test_estado_campana():
    r = llamar("estado_campana")
    assert r["mesas_totales"] == len(config.DIAS_CAMPANA) * config.MESAS_POR_DIA
    assert r["mesas_ocupadas"] == 3
    assert r["personas_esperadas"] == 9
    assert r["ingreso_proyectado"] == 3 * config.OFERTA["precio_oferta"]
    assert r["oferta"]["precio_oferta_texto"] == "₡17.900"
    assert r["oferta"]["ahorro_pct"] == 36.1
    assert r["estado"] == "activa"
    assert r["dias_restantes"] == (config.FECHA_LIMITE - HOY_FIJO).days


def test_cupos_por_dia():
    r = llamar("cupos_por_dia")
    assert len(r["dias"]) == len(config.DIAS_CAMPANA)
    primero = r["dias"][0]
    assert primero["ocupadas"] == 2 and primero["libres"] == 6
    assert primero["estado"] == "disponible"


def test_dias_vacios():
    r = llamar("dias_vacios", {"minimo_libres": 7})
    assert config.DIAS_CAMPANA[0].isoformat() not in [d["dia"] for d in r["dias"]]
    assert all(d["libres"] >= 7 for d in r["dias"])
    libres = [d["libres"] for d in r["dias"]]
    assert libres == sorted(libres, reverse=True)
    assert r["sugerencia"]


def test_listar_leads_enmascara():
    r = llamar("listar_leads", {"limite": 500})
    assert r["limite"] == 100
    assert r["cantidad"] == 3
    por_id = {x["whatsapp"]: x for x in r["reservas"]}
    assert "+506 ****-1234" in por_id
    assert por_id["+506 ****-1234"]["nombre"] == "Ana V."
    for x in r["reservas"]:
        assert "8888" not in x["whatsapp"]


def test_listar_leads_dia_invalido_y_filtro():
    assert "error" in llamar("listar_leads", {"dia": "05/12/2026"})
    r = llamar("listar_leads", {"dia": config.DIAS_CAMPANA[1].isoformat()})
    assert r["cantidad"] == 1


def test_resumen_campana():
    r = llamar("resumen_campana")
    assert r["totales"]["reservas"] == 3
    assert r["top_dias_reservados"][0]["dia"] == config.DIAS_CAMPANA[0].isoformat()
    assert len(r["dias_mas_vacios"]) == 3
    assert r["reservas_ultimas_24h"] == 3
    assert r["reservas_ultimos_7_dias"] == 3
    assert r["promedio_personas_por_reserva"] == 3.0
    assert r["datos_para_post"]["mesas_libres_dia_mas_vacio"] == 8


def test_datos_para_publicacion():
    r = llamar("datos_para_publicacion")
    assert r["mesas_libres"] == 8
    assert "No publicar sin aprobación del dueño" in r["reglas"]
    assert r["landing_url"] == "" and r["avisos"]
    r2 = llamar("datos_para_publicacion", {"dia": config.DIAS_CAMPANA[0].isoformat()})
    assert r2["mesas_libres"] == 6
    assert "error" in llamar("datos_para_publicacion", {"dia": "2026-12-25"})
