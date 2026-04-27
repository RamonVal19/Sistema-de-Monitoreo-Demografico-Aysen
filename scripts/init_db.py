"""
Script de inicialización — verifica la conexión y crea las tablas si no existen.

Uso:
    python scripts/init_db.py
"""

import sys
from sqlalchemy import text

# Importamos Base y engine DESPUÉS de que los modelos estén registrados
from api.database import engine, Base
import api.models  # noqa: F401 — necesario para que SQLAlchemy registre los modelos


def main() -> None:
    print("═" * 50)
    print("  Init DB — Monitoreo Demográfico Aysén")
    print("═" * 50)

    # 1. Prueba de conexión
    print("\n[1/2] Probando conexión a PostgreSQL...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.scalar()
        print(f"      ✅ Conectado: {version}")
    except Exception as exc:
        print(f"      ❌ Error de conexión: {exc}")
        sys.exit(1)

    # 2. Creación de tablas
    print("\n[2/2] Creando tablas (CREATE TABLE IF NOT EXISTS)...")
    try:
        Base.metadata.create_all(bind=engine)
        tablas = list(Base.metadata.tables.keys())
        for tabla in tablas:
            print(f"      ✅ {tabla}")
    except Exception as exc:
        print(f"      ❌ Error al crear tablas: {exc}")
        sys.exit(1)

    print("\n  Inicialización completada.\n")


if __name__ == "__main__":
    main()