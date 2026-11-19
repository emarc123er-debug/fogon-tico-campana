"""Datos de la campaña (negocio y cifras ficticios).

Aquí NO van claves ni secretos: todo lo sensible se lee de variables de entorno.
"""
from datetime import date

NEGOCIO = "El Fogón de Doña Tere"
CIUDAD = "Heredia, Costa Rica"

OFERTA = {
    "nombre": "Cena Navideña Tica para 2",
    "incluye": [
        "2 tamales de cerdo envueltos en hoja de plátano",
        "Gallos de chicharrón con tortillas palmeadas",
        "Ensalada rusa de la casa",
        "Queque navideño",
        "2 vasos de rompope casero",
    ],
    "precio_ancla": 28000,   # colones
    "precio_oferta": 17900,  # colones, por pareja
    "moneda": "CRC",
}

MESAS_POR_DIA = 8
PERSONAS_MIN = 2
PERSONAS_MAX = 6

# Viernes, sábados y domingos de diciembre 2026
DIAS_CAMPANA = [
    date(2026, 12, 4), date(2026, 12, 5), date(2026, 12, 6),
    date(2026, 12, 11), date(2026, 12, 12), date(2026, 12, 13),
    date(2026, 12, 18), date(2026, 12, 19), date(2026, 12, 20),
]

FECHA_LIMITE = date(2026, 12, 17)  # último día para reservar

DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_bonita(d: date) -> str:
    """'viernes 4 de diciembre'"""
    return f"{DIAS_SEMANA[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


def colones(monto: int) -> str:
    """17900 -> '₡17.900'"""
    return "₡" + f"{monto:,}".replace(",", ".")
