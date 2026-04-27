"""
Script de carga de datos — CSV del ETL → PostgreSQL.

Lee los archivos procesados en data/ e inserta los registros en las tablas
'comunas' e 'indicadores_demograficos'. Es idempotente: si los datos ya
existen (por la UniqueConstraint), los omite sin fallar.

Uso:
    python scripts/load_data.py [--anio 2024] [--anio 2017]
    python scripts/load_data.py          # carga ambos años por defecto
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Añadimos la raíz del proyecto al path para que los imports de 'api/' funcionen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.database import SessionLocal, engine, Base  # noqa: E402
import api.models  # noqa: F401, E402 — registra los modelos en Base.metadata
from api.models import Comuna, IndicadorDemografico  # noqa: E402

# ── Rutas de los CSV ──────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

ARCHIVOS = {
    2017: DATA_DIR / "personas_censo2017.csv",
    2024: DATA_DIR / "censo_2024_aysen_final.csv",
}

# Columnas que esperamos en ambos CSV (mínimo necesario)
COLS_REQUERIDAS = {"region", "comuna", "sexo", "edad", "edad_quinquenal",
                   "nombre_comuna", "sexo_label"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validar_columnas(df: pd.DataFrame, ruta: Path) -> None:
    faltantes = COLS_REQUERIDAS - set(df.columns)
    if faltantes:
        raise ValueError(
            f"El archivo '{ruta.name}' no tiene las columnas esperadas: {faltantes}"
        )


def _upsert_comunas(df: pd.DataFrame, db) -> int:
    """Inserta comunas nuevas; omite las que ya existen (por PK)."""
    catalogo = (
        df[["comuna", "nombre_comuna"]]
        .drop_duplicates(subset="comuna")
        .rename(columns={"comuna": "codigo_comuna"})
        .assign(codigo_region=11)
    )
    insertadas = 0
    for _, row in catalogo.iterrows():
        stmt = (
            pg_insert(Comuna)
            .values(
                codigo_comuna=int(row["codigo_comuna"]),
                nombre_comuna=str(row["nombre_comuna"]),
                codigo_region=11,
            )
            .on_conflict_do_nothing(index_elements=["codigo_comuna"])
        )
        result = db.execute(stmt)
        insertadas += result.rowcount
    return insertadas


def _upsert_indicadores(df: pd.DataFrame, anio: int, db) -> int:
    """
    Inserta registros de indicadores en lotes de 1000 filas.
    Los duplicados (UniqueConstraint) se omiten silenciosamente.
    """
    registros = df[["comuna", "sexo", "sexo_label", "edad", "edad_quinquenal"]].copy()
    registros = registros.rename(columns={"comuna": "codigo_comuna"})
    registros["anio_censo"] = anio

    # Convertir a tipos nativos de Python para evitar errores de numpy int64
    registros["codigo_comuna"] = registros["codigo_comuna"].astype(int)
    registros["sexo"] = registros["sexo"].astype(int)
    registros["edad"] = registros["edad"].astype(int)
    registros["edad_quinquenal"] = registros["edad_quinquenal"].astype(int)

    total_insertados = 0
    lote = 1_000

    for inicio in range(0, len(registros), lote):
        bloque = registros.iloc[inicio: inicio + lote].to_dict(orient="records")
        stmt = (
            pg_insert(IndicadorDemografico)
            .values(bloque)
            .on_conflict_do_nothing(
                constraint="uq_registro_censal"
            )
        )
        result = db.execute(stmt)
        total_insertados += result.rowcount

    return total_insertados


# ── Función principal ─────────────────────────────────────────────────────────

def cargar_anio(anio: int) -> None:
    ruta = ARCHIVOS[anio]

    print(f"\n  [{anio}] Leyendo {ruta.name} ...")
    if not ruta.exists():
        print(f"         ⚠️  Archivo no encontrado: {ruta} — omitiendo.")
        return

    df = pd.read_csv(ruta, dtype={"comuna": int, "sexo": int, "edad": int,
                                   "edad_quinquenal": int})
    _validar_columnas(df, ruta)

    # Filtrar solo registros de la región 11 (Aysén) por si el CSV es nacional
    df = df[df["region"] == 11].copy()
    print(f"         Filas filtradas región 11: {len(df):,}")

    db = SessionLocal()
    try:
        print(f"         Cargando catálogo de comunas ...", end=" ")
        n_comunas = _upsert_comunas(df, db)
        db.commit()
        print(f"✅ {n_comunas} nuevas")

        print(f"         Cargando indicadores demográficos ...", end=" ")
        n_ind = _upsert_indicadores(df, anio, db)
        db.commit()
        print(f"✅ {n_ind:,} nuevos registros")

    except Exception as exc:
        db.rollback()
        print(f"\n         ❌ Error durante la carga: {exc}")
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carga los CSV del ETL en PostgreSQL."
    )
    parser.add_argument(
        "--anio", type=int, choices=[2017, 2024], action="append",
        help="Año(s) a cargar. Sin este flag se cargan ambos."
    )
    args = parser.parse_args()

    anios = args.anio if args.anio else [2017, 2024]

    print("═" * 50)
    print("  Load Data — Monitoreo Demográfico Aysén")
    print("═" * 50)

    # Asegurar que las tablas existen antes de insertar
    Base.metadata.create_all(bind=engine)

    for anio in anios:
        cargar_anio(anio)

    print("\n  Carga completada.\n")


if __name__ == "__main__":
    main()