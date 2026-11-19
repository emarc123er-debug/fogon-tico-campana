"""Servidor MCP de la campaña "Cena Navideña Tica para 2" (datos ficticios).

Expone herramientas de SOLO LECTURA para que el dueño pregunte a Claude cosas como
"¿Qué días siguen vacíos?" y Claude redacte publicaciones con datos reales.

- Local (stdio):   python -m app.mcp_server
- En producción:   app/main.py monta  mcp.http_app(path="/mcp")  (Streamable HTTP).

No hay claves en este archivo: la base de datos y la URL de la landing se leen de
variables de entorno (DATABASE_URL, LANDING_URL).
"""
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastmcp import FastMCP

from . import analytics, config, db

TZ = ZoneInfo("America/Costa_Rica")
SOLO_LECTURA = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}
LIMITE_MAX = 100

REGLAS_PUBLICACION = [
    "Usar solo estos datos reales",
    "No publicar sin aprobación del dueño",
    "Publicar solo en cuenta de prueba",
]

mcp = FastMCP(
    name="Fogon Tico Campaña",
    instructions=(
        f"Servidor de la campaña '{config.OFERTA['nombre']}' de {config.NEGOCIO} "
        f"({config.CIUDAD}). El negocio y los datos son FICTICIOS (proyecto de clase). "
        "Todas las herramientas son de solo lectura:\n"
        "- estado_campana: oferta, precios, fecha límite, ocupación total e ingreso proyectado.\n"
        "- cupos_por_dia: mesas libres/ocupadas por día con su estado.\n"
        "- dias_vacios: días futuros con más mesas libres (para decidir qué día promocionar).\n"
        "- listar_leads: reservas recientes con datos personales enmascarados.\n"
        "- resumen_campana: informe listo para reportar + datos_para_post.\n"
        "- datos_para_publicacion: datos reales para redactar una publicación en redes.\n"
        "Reglas: usa solo los datos que devuelven las herramientas (no inventes cifras); "
        "cualquier publicación debe mostrarse como borrador y ser APROBADA por el dueño "
        "antes de publicarse, y solo en la cuenta de prueba. Moneda: colones (CRC)."
    ),
)


# ---------------------------------------------------------------- utilidades

def _hoy() -> date:
    """Fecha actual en Costa Rica."""
    return datetime.now(TZ).date()


def _estado_dia(d: date, libres: int, hoy: date) -> str:
    if d < hoy:
        return "pasado"
    if libres <= 0:
        return "agotado"
    if libres <= 2:
        return "últimas mesas"
    return "disponible"


def _cupos(hoy: date) -> list[dict]:
    out = []
    for c in db.cupos_por_dia():
        d = date.fromisoformat(c["dia"])
        out.append({**c, "estado": _estado_dia(d, c["libres"], hoy)})
    return out


def _futuros(cupos: list[dict], hoy: date) -> list[dict]:
    return [c for c in cupos if date.fromisoformat(c["dia"]) >= hoy]


def _mas_vacios(cupos: list[dict]) -> list[dict]:
    """Ordena de más vacío a menos; a igualdad, el día más cercano primero."""
    return sorted(cupos, key=lambda c: (-c["libres"], c["dia"]))


def _parse_dia(dia: str) -> tuple[date | None, dict | None]:
    try:
        return date.fromisoformat(dia.strip()), None
    except (ValueError, AttributeError):
        return None, {
            "error": f"Fecha inválida: '{dia}'. Usa formato ISO AAAA-MM-DD (ej. 2026-12-05).",
            "dias_validos": [d.isoformat() for d in config.DIAS_CAMPANA],
        }


def _info_limite(hoy: date) -> dict:
    return {
        "fecha_limite": config.FECHA_LIMITE.isoformat(),
        "fecha_limite_texto": config.fecha_bonita(config.FECHA_LIMITE),
        "dias_restantes": max((config.FECHA_LIMITE - hoy).days, 0),
    }


def _precios() -> dict:
    o = config.OFERTA
    ahorro = o["precio_ancla"] - o["precio_oferta"]
    return {
        "precio_ancla": o["precio_ancla"],
        "precio_ancla_texto": config.colones(o["precio_ancla"]),
        "precio_oferta": o["precio_oferta"],
        "precio_oferta_texto": config.colones(o["precio_oferta"]),
        "ahorro": ahorro,
        "ahorro_texto": config.colones(ahorro),
        "ahorro_pct": round(ahorro * 100 / o["precio_ancla"], 1),
        "moneda": o["moneda"],
    }


def _estado_campana(hoy: date, cupos: list[dict]) -> str:
    if hoy > config.FECHA_LIMITE:
        return "cerrada"
    if sum(c["libres"] for c in _futuros(cupos, hoy)) == 0:
        return "agotada"
    return "activa"


def _enmascarar_whatsapp(numero: str) -> str:
    digitos = "".join(ch for ch in str(numero) if ch.isdigit())
    ultimos = digitos[-4:] if len(digitos) >= 4 else "****"
    if digitos.startswith("506") and len(digitos) == 11:
        return f"+506 ****-{ultimos}"
    return f"****-{ultimos}"


def _nombre_corto(nombre: str) -> str:
    partes = str(nombre).split()
    if not partes:
        return "(sin nombre)"
    if len(partes) == 1:
        return partes[0]
    return f"{partes[0]} {partes[1][0].upper()}."


def _iso(valor):
    if isinstance(valor, datetime):
        if valor.tzinfo is None:  # SQLite guarda en UTC sin zona
            valor = valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(TZ).isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


def _estado(hoy: date, cupos: list[dict]) -> dict:
    totales = sum(c["mesas_totales"] for c in cupos)
    ocupadas = sum(c["ocupadas"] for c in cupos)
    personas = sum(analytics.personas_por_dia().values())
    ingreso = ocupadas * config.OFERTA["precio_oferta"]
    return {
        "negocio": config.NEGOCIO,
        "ciudad": config.CIUDAD,
        "datos_ficticios": True,
        "hoy": hoy.isoformat(),
        "oferta": {
            "nombre": config.OFERTA["nombre"],
            "incluye": config.OFERTA["incluye"],
            **_precios(),
        },
        **_info_limite(hoy),
        "dias_campana": len(cupos),
        "mesas_por_dia": config.MESAS_POR_DIA,
        "mesas_totales": totales,
        "mesas_ocupadas": ocupadas,
        "mesas_libres": totales - ocupadas,
        "ocupacion_pct": round(ocupadas * 100 / totales, 1) if totales else 0.0,
        "personas_esperadas": personas,
        "ingreso_proyectado": ingreso,
        "ingreso_proyectado_texto": config.colones(ingreso),
        "nota_ingreso": "Reservas × precio de oferta (una cena para 2 por reserva).",
        "estado": _estado_campana(hoy, cupos),
    }


# ---------------------------------------------------------------- herramientas

@mcp.tool(annotations=SOLO_LECTURA)
def estado_campana() -> dict:
    """Estado general de la campaña: oferta, precios (ancla y oferta en colones), % de
    ahorro, fecha límite y días restantes, mesas totales/ocupadas/libres, % de ocupación,
    personas esperadas, ingreso proyectado y estado (activa / cerrada / agotada)."""
    hoy = _hoy()
    return _estado(hoy, _cupos(hoy))


@mcp.tool(annotations=SOLO_LECTURA)
def cupos_por_dia(solo_con_cupo: bool = False) -> dict:
    """Disponibilidad por día de campaña: mesas totales, ocupadas y libres, con estado
    'agotado', 'últimas mesas' (2 o menos), 'disponible' o 'pasado'.
    Con solo_con_cupo=True devuelve solo días futuros que aún tienen mesas libres."""
    hoy = _hoy()
    cupos = _cupos(hoy)
    if solo_con_cupo:
        cupos = [c for c in cupos if c["estado"] in ("disponible", "últimas mesas")]
    return {"hoy": hoy.isoformat(), "dias": cupos}


@mcp.tool(annotations=SOLO_LECTURA)
def dias_vacios(minimo_libres: int = 4) -> dict:
    """Días futuros con al menos `minimo_libres` mesas libres, ordenados del más vacío
    al menos vacío. Útil para decidir qué día promocionar en redes."""
    hoy = _hoy()
    minimo = max(int(minimo_libres), 0)
    candidatos = [c for c in _futuros(_cupos(hoy), hoy) if c["libres"] >= minimo]
    candidatos = _mas_vacios(candidatos)
    if hoy > config.FECHA_LIMITE:
        sugerencia = "La fecha límite de reservas ya pasó; no conviene promocionar."
    elif candidatos:
        top = candidatos[0]
        sugerencia = (f"Promocionar el {top['dia_texto']}: tiene {top['libres']} de "
                      f"{top['mesas_totales']} mesas libres.")
    else:
        sugerencia = (f"Ningún día futuro tiene {minimo} o más mesas libres; "
                      "prueba con un mínimo menor.")
    return {
        "hoy": hoy.isoformat(),
        "minimo_libres": minimo,
        "dias": candidatos,
        "sugerencia": sugerencia,
    }


@mcp.tool(annotations=SOLO_LECTURA)
def listar_leads(dia: str | None = None, limite: int = 20) -> dict:
    """Reservas recientes (más nuevas primero). Filtra por `dia` (AAAA-MM-DD) si se indica.
    Privacidad: solo nombre + inicial del apellido y WhatsApp enmascarado (últimos 4).
    `limite` máximo 100."""
    filtro = None
    if dia:
        filtro, error = _parse_dia(dia)
        if error:
            return error
    limite = min(max(int(limite), 1), LIMITE_MAX)
    filas = db.obtener_leads(dia=filtro, limite=limite)
    reservas = [{
        "id": f["id"],
        "nombre": _nombre_corto(f["nombre"]),
        "whatsapp": _enmascarar_whatsapp(f["whatsapp"]),
        "personas": f["personas"],
        "dia": _iso(f["dia"]),
        "dia_texto": config.fecha_bonita(f["dia"]),
        "creado": _iso(f["creado"]),
    } for f in filas]
    return {
        "filtro_dia": filtro.isoformat() if filtro else None,
        "limite": limite,
        "cantidad": len(reservas),
        "reservas": reservas,
        "nota_privacidad": "Datos personales enmascarados.",
    }


@mcp.tool(annotations=SOLO_LECTURA)
def resumen_campana() -> dict:
    """Resumen listo para informe: totales, 3 días más reservados, 3 días futuros más
    vacíos, reservas de las últimas 24 h y 7 días, tamaño promedio de grupo y
    `datos_para_post` (datos reales para redactar una publicación)."""
    hoy = _hoy()
    cupos = _cupos(hoy)
    estado = _estado(hoy, cupos)
    ahora = datetime.now(timezone.utc)
    reservados = sorted([c for c in cupos if c["ocupadas"] > 0],
                        key=lambda c: (-c["ocupadas"], c["dia"]))[:3]
    vacios = _mas_vacios([c for c in _futuros(cupos, hoy) if c["libres"] > 0])[:3]
    mas_vacio = vacios[0] if vacios else None
    return {
        "hoy": hoy.isoformat(),
        "estado": estado["estado"],
        "totales": {
            "reservas": estado["mesas_ocupadas"],
            "mesas_totales": estado["mesas_totales"],
            "mesas_libres": estado["mesas_libres"],
            "ocupacion_pct": estado["ocupacion_pct"],
            "personas_esperadas": estado["personas_esperadas"],
            "ingreso_proyectado": estado["ingreso_proyectado"],
            "ingreso_proyectado_texto": estado["ingreso_proyectado_texto"],
        },
        "top_dias_reservados": reservados,
        "dias_mas_vacios": vacios,
        "reservas_ultimas_24h": analytics.reservas_desde(ahora - timedelta(hours=24)),
        "reservas_ultimos_7_dias": analytics.reservas_desde(ahora - timedelta(days=7)),
        "promedio_personas_por_reserva": analytics.tamano_promedio_grupo(),
        "datos_para_post": {
            "oferta": config.OFERTA["nombre"],
            "negocio": config.NEGOCIO,
            "precio_oferta_texto": config.colones(config.OFERTA["precio_oferta"]),
            "precio_ancla_texto": config.colones(config.OFERTA["precio_ancla"]),
            "dia_mas_vacio": mas_vacio["dia_texto"] if mas_vacio else None,
            "mesas_libres_dia_mas_vacio": mas_vacio["libres"] if mas_vacio else 0,
            "fecha_limite_texto": config.fecha_bonita(config.FECHA_LIMITE),
            "nota": "Usar solo estos datos; el post requiere aprobación del dueño.",
        },
    }


@mcp.tool(annotations=SOLO_LECTURA)
def datos_para_publicacion(dia: str | None = None) -> dict:
    """Datos REALES para redactar una publicación en redes sobre un día (AAAA-MM-DD) o,
    si no se indica, sobre el día futuro con más mesas libres. Incluye precio, ancla,
    mesas libres, fecha límite, URL de la landing y reglas que se deben respetar."""
    hoy = _hoy()
    cupos = _cupos(hoy)
    if dia:
        objetivo, error = _parse_dia(dia)
        if error:
            return error
        elegido = next((c for c in cupos if c["dia"] == objetivo.isoformat()), None)
        if elegido is None:
            return {
                "error": f"{objetivo.isoformat()} no es un día de la campaña.",
                "dias_validos": [c["dia"] for c in cupos],
            }
    else:
        disponibles = [c for c in _futuros(cupos, hoy) if c["libres"] > 0]
        if not disponibles:
            return {"error": "No hay días futuros con mesas libres; no hay nada que promocionar."}
        elegido = _mas_vacios(disponibles)[0]

    # LANDING_URL manual, o la URL pública que Render asigna automáticamente
    landing = (os.getenv("LANDING_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").strip()
    avisos = []
    if not landing:
        avisos.append("LANDING_URL no está configurada; pide la URL al dueño antes de publicar.")
    if elegido["estado"] in ("agotado", "pasado"):
        avisos.append(f"Este día está '{elegido['estado']}': no conviene promocionarlo.")
    if hoy > config.FECHA_LIMITE:
        avisos.append("La fecha límite de reservas ya pasó.")

    return {
        "negocio": config.NEGOCIO,
        "ciudad": config.CIUDAD,
        "oferta": config.OFERTA["nombre"],
        "incluye": config.OFERTA["incluye"],
        "dia": elegido["dia"],
        "dia_texto": elegido["dia_texto"],
        "mesas_libres": elegido["libres"],
        "mesas_totales": elegido["mesas_totales"],
        "estado_dia": elegido["estado"],
        **_precios(),
        **_info_limite(hoy),
        "landing_url": landing,
        "avisos": avisos,
        "reglas": REGLAS_PUBLICACION,
    }


if __name__ == "__main__":
    from .db import init_db
    init_db()
    mcp.run()  # stdio, para pruebas locales con Claude Desktop / inspector
