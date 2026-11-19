"""Landing de la campaña: página principal y API de cupos/reservas.

`app/main.py` hace `app.include_router(landing.router)` y monta `/static`.
"""
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import config, db

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

ZONA_CR = ZoneInfo("America/Costa_Rica")


def hoy_cr() -> date:
    """Fecha de hoy en Costa Rica (no la del servidor)."""
    return datetime.now(ZONA_CR).date()


def estado_cupos(hoy: date) -> dict:
    """Cupos por día enriquecidos con banderas útiles para la vista."""
    cerrado_por_fecha = hoy > config.FECHA_LIMITE
    dias = []
    for c in db.cupos_por_dia():
        d = date.fromisoformat(c["dia"])
        pasado = d < hoy
        c["pasado"] = pasado
        c["reservable"] = (not pasado) and (not cerrado_por_fecha) and c["libres"] > 0
        dias.append(c)
    total_libres = sum(c["libres"] for c in dias if not c["pasado"])
    return {
        "cupos": dias,
        "total_libres": 0 if cerrado_por_fecha else total_libres,
        "cerrado": cerrado_por_fecha or total_libres == 0,
        "dias_restantes": max((config.FECHA_LIMITE - hoy).days, 0),
    }


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    hoy = hoy_cr()
    estado = estado_cupos(hoy)
    oferta = config.OFERTA
    ahorro = round((1 - oferta["precio_oferta"] / oferta["precio_ancla"]) * 100)
    contexto = {
        "negocio": config.NEGOCIO,
        "ciudad": config.CIUDAD,
        "oferta": oferta,
        "precio_ancla": config.colones(oferta["precio_ancla"]),
        "precio_oferta": config.colones(oferta["precio_oferta"]),
        "ahorro_pct": ahorro,
        "mesas_por_dia": config.MESAS_POR_DIA,
        "personas_min": config.PERSONAS_MIN,
        "personas_max": config.PERSONAS_MAX,
        "fecha_limite": config.FECHA_LIMITE.isoformat(),
        "fecha_limite_texto": config.fecha_bonita(config.FECHA_LIMITE),
        "dias_disponibles": [c for c in estado["cupos"] if c["reservable"]],
        **estado,
    }
    return templates.TemplateResponse(request, "index.html", contexto)


@router.get("/api/cupos")
def api_cupos():
    estado = estado_cupos(hoy_cr())
    return {
        "cupos": estado["cupos"],
        "total_libres": estado["total_libres"],
        "cerrado": estado["cerrado"],
        "dias_restantes": estado["dias_restantes"],
    }


class Reserva(BaseModel):
    """Campos tolerantes: la validación fina se hace a mano para dar mensajes claros."""
    nombre: str | None = None
    whatsapp: str | int | None = None
    personas: int | str | None = None
    dia: str | None = None
    empresa: str | None = None  # honeypot: los humanos no lo ven


def _error(mensaje: str, status: int = 422) -> JSONResponse:
    return JSONResponse(status_code=status, content={"ok": False, "detail": mensaje})


def _normalizar_whatsapp(valor) -> str | None:
    """Devuelve '+506XXXXXXXX' o None si no es un celular tico válido."""
    if valor is None:
        return None
    limpio = re.sub(r"[\s\-().]", "", str(valor))
    if limpio.startswith("+506"):
        limpio = limpio[4:]
    elif limpio.startswith("00506"):
        limpio = limpio[5:]
    elif limpio.startswith("506") and len(limpio) == 11:
        limpio = limpio[3:]
    if re.fullmatch(r"[5-8]\d{7}", limpio):
        return "+506" + limpio
    return None


@router.post("/api/reservas", status_code=201)
def api_reservas(reserva: Reserva):
    # Honeypot: si un bot llenó el campo oculto, fingimos éxito sin guardar
    if reserva.empresa and reserva.empresa.strip():
        return JSONResponse(status_code=200, content={"ok": True, "mensaje": "¡Gracias! Recibimos su solicitud."})

    hoy = hoy_cr()
    if hoy > config.FECHA_LIMITE:
        return _error("Las reservas para esta campaña ya cerraron. ¡Gracias por su interés!")

    nombre = (reserva.nombre or "").strip()
    nombre = re.sub(r"\s+", " ", nombre)
    if not 2 <= len(nombre) <= 80:
        return _error("Por favor escriba su nombre (entre 2 y 80 caracteres).")

    whatsapp = _normalizar_whatsapp(reserva.whatsapp)
    if not whatsapp:
        return _error("El WhatsApp debe ser un celular de Costa Rica de 8 dígitos (empieza con 5, 6, 7 u 8).")

    try:
        personas = int(str(reserva.personas).strip())
    except (TypeError, ValueError):
        personas = None
    if personas is None or not config.PERSONAS_MIN <= personas <= config.PERSONAS_MAX:
        return _error(f"La mesa es para {config.PERSONAS_MIN} a {config.PERSONAS_MAX} personas.")

    try:
        dia = date.fromisoformat((reserva.dia or "").strip())
    except ValueError:
        dia = None
    if dia is None or dia not in config.DIAS_CAMPANA:
        return _error("Elija uno de los días disponibles de la campaña.")
    if dia < hoy:
        return _error("Ese día ya pasó. Por favor elija otra fecha.")

    try:
        nuevo_id = db.crear_lead(nombre, whatsapp, personas, dia)
    except db.SinCupo:
        return _error(
            f"¡Qué pena! Ya no quedan mesas para el {config.fecha_bonita(dia)}. Pruebe con otro día.",
            status=409,
        )
    except Exception:
        # Nunca mostramos el error interno al usuario
        return _error("No pudimos guardar su reserva en este momento. Intente de nuevo en unos minutos.", status=500)

    libres_dia = next(
        (c["libres"] for c in db.cupos_por_dia() if c["dia"] == dia.isoformat()), 0
    )
    primer_nombre = nombre.split(" ")[0]
    return JSONResponse(status_code=201, content={
        "ok": True,
        "id": nuevo_id,
        "mensaje": (
            f"¡Listo, {primer_nombre}! Su mesa para el {config.fecha_bonita(dia)} quedó apartada. "
            f"Le escribiremos al WhatsApp {whatsapp} para confirmar."
        ),
        "libres_restantes_del_dia": libres_dia,
    })
