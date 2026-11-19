"""Carga reservas FICTICIAS de demostración en la base de datos.

Uso (desde la raíz del proyecto):
    python -m scripts.seed_demo            # solo si la tabla está vacía
    python -m scripts.seed_demo --force    # borra todas las reservas y vuelve a sembrar

Usa la misma DATABASE_URL que la app (o leads.db en local). Nombres y números
son inventados (+50688880001, +50688880002, ...).
"""
import argparse
import random
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app import config
from app.db import engine, init_db, leads

NOMBRES = ["María", "José", "Ana", "Luis", "Carolina", "Andrés", "Daniela", "Carlos",
           "Sofía", "Esteban", "Valeria", "Diego", "Mariela", "Pablo", "Gabriela",
           "Fabián", "Natalia", "Rodrigo", "Melissa", "Jorge", "Priscilla", "Mauricio"]
APELLIDOS = ["Rodríguez", "Jiménez", "Mora", "Vargas", "Solano", "Araya", "Quesada",
             "Chaves", "Rojas", "Alfaro", "Calderón", "Brenes", "Monge", "Ulate",
             "Salazar", "Castro", "Zúñiga", "Arias", "Villalobos", "Méndez"]

# Ocupación deseada por día (en el orden de config.DIAS_CAMPANA): desigual a propósito,
# algunos casi llenos y otros vacíos. Nunca supera MESAS_POR_DIA.
OCUPACION = [7, 8, 6, 3, 5, 1, 4, 0, 2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Siembra reservas ficticias de demo.")
    parser.add_argument("--force", action="store_true",
                        help="Borra TODAS las reservas existentes antes de sembrar.")
    parser.add_argument("--semilla", type=int, default=2026, help="Semilla aleatoria.")
    args = parser.parse_args()

    init_db()
    with engine.connect() as conn:
        existentes = conn.execute(select(func.count()).select_from(leads)).scalar_one()
    if existentes and not args.force:
        print(f"La tabla 'leads' ya tiene {existentes} reservas. "
              "No se hizo nada (usa --force para borrar y volver a sembrar).")
        return 1

    rnd = random.Random(args.semilla)
    ahora = datetime.now(timezone.utc)
    filas = []
    n = 0
    for dia, cantidad in zip(config.DIAS_CAMPANA, OCUPACION):
        for _ in range(min(cantidad, config.MESAS_POR_DIA)):
            n += 1
            filas.append({
                "nombre": f"{rnd.choice(NOMBRES)} {rnd.choice(APELLIDOS)} {rnd.choice(APELLIDOS)}",
                "whatsapp": f"+5068888{n:04d}",
                "personas": rnd.choice([2, 2, 2, 3, 4, 4, 5, 6]),
                "dia": dia,
                # repartidas en los últimos 10 días
                "creado": ahora - timedelta(minutes=rnd.randint(30, 10 * 24 * 60)),
            })

    with engine.begin() as conn:
        if existentes:
            conn.execute(delete(leads))
            print(f"--force: se borraron {existentes} reservas existentes.")
        if filas:
            conn.execute(leads.insert(), filas)

    print(f"Se sembraron {len(filas)} reservas ficticias en {engine.url.render_as_string(hide_password=True)}")
    print(f"{'Día':<28}{'Ocupadas':>9}{'Libres':>8}")
    for dia, cantidad in zip(config.DIAS_CAMPANA, OCUPACION):
        ocup = min(cantidad, config.MESAS_POR_DIA)
        print(f"{config.fecha_bonita(dia):<28}{ocup:>9}{config.MESAS_POR_DIA - ocup:>8}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
