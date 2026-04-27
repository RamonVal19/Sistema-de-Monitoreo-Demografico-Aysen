"""
etl/pipeline.py
───────────────
Pipeline ETL en Python puro (sin Jupyter) para RF1:
  Descarga, limpieza y carga automática de archivos CSV del INE en PostgreSQL.

Pasos:
  E — Extracción   : lectura de CSVs del INE (2017 y/o 2024)
  T — Transformación: filtro región 11, limpieza de tipos, mapeo de etiquetas,
                      edades reservadas → NULL
  L — Carga         : upsert en PostgreSQL (comunas + indicadores_demograficos)

Uso:
    python etl/pipeline.py                   # procesa 2017 y 2024
    python etl/pipeline.py --anio 2024       # solo 2024
    python etl/pipeline.py --dry-run         # transforma sin cargar en BD
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy.dialects.postgresql import insert as pg_insert

# ── Path al raíz del proyecto para imports de api/ ───────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.database import SessionLocal, engine, Base  # noqa: E402
import api.models  # noqa: F401, E402
from api.models import Comuna, IndicadorDemografico  # noqa: E402

# ── Constantes del dominio (fuente única de verdad) ──────────────────────────
REGION_AYSEN = 11

COMUNAS_AYSEN: dict[int, str] = {
    11101: "Coyhaique",
    11102: "Lago Verde",
    11201: "Aysén",
    11202: "Cisnes",
    11203: "Guaitecas",
    11301: "Cochrane",
    11302: "O'Higgins",
    11303: "Tortel",
    11401: "Chile Chico",
    11402: "Río Ibáñez",
}

SEXO_LABEL: dict[int, str] = {1: "Hombre", 2: "Mujer"}

# Edad usada por el INE para marcar "prefiero no responder"
EDAD_RESERVADA = -66

# Columnas mínimas que debe tener cualquier CSV de entrada
COLS_REQUERIDAS = {"region", "comuna", "sexo", "edad", "edad_quinquenal"}


# ═════════════════════════════════════════════════════════════════════════════
# E — EXTRACCIÓN
# ═════════════════════════════════════════════════════════════════════════════

def extraer_2017(ruta: Path) -> pd.DataFrame:
    """
    Carga el CSV 2017 (ya filtrado por Aysén, separador coma).
    Devuelve un DataFrame crudo sin transformar.
    """
    print(f"    Leyendo {ruta.name} ...")
    df = pd.read_csv(ruta, sep=",", low_memory=False)
    print(f"    Registros cargados: {len(df):,}")
    return df


def extraer_2024(ruta: Path) -> pd.DataFrame:
    """
    Carga el CSV 2024 (nacional, separador punto y coma) en chunks de 100k
    y filtra directamente por región 11 para no saturar RAM.
    """
    cols = list(COLS_REQUERIDAS)  # solo columnas necesarias
    print(f"    Leyendo {ruta.name} en chunks ...")

    bloques: list[pd.DataFrame] = []
    lector = pd.read_csv(
        ruta,
        sep=";",
        usecols=cols,
        chunksize=100_000,
        low_memory=False,
    )
    for i, chunk in enumerate(lector):
        aysen = chunk[chunk["region"] == REGION_AYSEN]
        if not aysen.empty:
            bloques.append(aysen)
        if i % 10 == 0:
            print(f"      chunk {i} procesado ...")

    df = pd.concat(bloques, ignore_index=True)
    print(f"    Registros región 11 encontrados: {len(df):,}")
    return df


# ═════════════════════════════════════════════════════════════════════════════
# T — TRANSFORMACIÓN
# ═════════════════════════════════════════════════════════════════════════════

def _validar_columnas(df: pd.DataFrame, nombre_archivo: str) -> None:
    faltantes = COLS_REQUERIDAS - set(df.columns)
    if faltantes:
        raise ValueError(
            f"'{nombre_archivo}' no tiene las columnas requeridas: {faltantes}"
        )


def transformar(df: pd.DataFrame, anio: int) -> pd.DataFrame:
    """
    Aplica todas las transformaciones de limpieza y normalización.

    Decisiones de limpieza documentadas:
      - Edades reservadas (valor -66 del INE) → NULL (pd.NA)
        Razón: -66 no es un dato demográfico real; NULL permite filtrarlos
        limpiamente en SQL sin afectar los cálculos de indicadores.
      - Comunas no mapeadas → se descartan (no pertenecen a Aysén).
      - Sexo no mapeado    → se descarta (valor fuera del dominio 1/2).
      - edad_quinquenal    → int16 (rango 0–85, ahorra memoria).
    """
    _validar_columnas(df, f"censo_{anio}")

    resultado = df.copy()

    # ── 1. Filtro región ──────────────────────────────────────────────────────
    resultado = resultado[resultado["region"] == REGION_AYSEN].copy()

    # ── 2. Tipos base ─────────────────────────────────────────────────────────
    resultado["comuna"] = resultado["comuna"].astype(int)
    resultado["sexo"] = resultado["sexo"].astype(int)
    resultado["edad_quinquenal"] = resultado["edad_quinquenal"].astype(int)

    # ── 3. Edad: reservada → NULL ─────────────────────────────────────────────
    edad_numerica = pd.to_numeric(resultado["edad"], errors="coerce")
    resultado["edad"] = edad_numerica.where(edad_numerica != EDAD_RESERVADA, other=pd.NA)
    # Convertir a Int64 (nullable integer) para soportar pd.NA
    resultado["edad"] = resultado["edad"].astype("Int64")

    # ── 4. Mapeo de etiquetas ─────────────────────────────────────────────────
    resultado["nombre_comuna"] = resultado["comuna"].map(COMUNAS_AYSEN)
    resultado["sexo_label"] = resultado["sexo"].map(SEXO_LABEL)

    # ── 5. Control de calidad ─────────────────────────────────────────────────
    n_antes = len(resultado)
    resultado.dropna(subset=["nombre_comuna", "sexo_label"], inplace=True)
    n_descartados = n_antes - len(resultado)
    if n_descartados > 0:
        print(f"    ⚠️  {n_descartados} registros descartados "
              f"(comuna o sexo fuera del dominio).")

    n_edad_null = resultado["edad"].isna().sum()
    print(f"    Edades reservadas → NULL: {n_edad_null:,}")
    print(f"    Registros limpios:        {len(resultado):,}")

    return resultado


# ═════════════════════════════════════════════════════════════════════════════
# L — CARGA
# ═════════════════════════════════════════════════════════════════════════════

def _cargar_comunas(db) -> None:
    """Upsert del catálogo de comunas (idempotente)."""
    for codigo, nombre in COMUNAS_AYSEN.items():
        stmt = (
            pg_insert(Comuna)
            .values(codigo_comuna=codigo, nombre_comuna=nombre, codigo_region=11)
            .on_conflict_do_nothing(index_elements=["codigo_comuna"])
        )
        db.execute(stmt)
    db.commit()
    print(f"    Catálogo de comunas: {len(COMUNAS_AYSEN)} registros sincronizados.")

def _cargar_indicadores(df: pd.DataFrame, anio: int, db) -> int:
    cols_insertar = ["comuna", "sexo", "sexo_label", "edad", "edad_quinquenal"]
    registros = df[cols_insertar].rename(columns={"comuna": "codigo_comuna"}).copy()
    registros["anio_censo"] = anio

    total_insertados = 0
    lote = 2_000

    for inicio in range(0, len(registros), lote):
        bloque = registros.iloc[inicio: inicio + lote]
        filas = []
        for fila in bloque.itertuples(index=False):
            filas.append({
                "codigo_comuna":   int(fila.codigo_comuna),
                "anio_censo":      anio,
                "sexo":            int(fila.sexo),
                "sexo_label":      str(fila.sexo_label),
                "edad":            None if pd.isna(fila.edad) else int(fila.edad),
                "edad_quinquenal": int(fila.edad_quinquenal),
            })
        db.execute(IndicadorDemografico.__table__.insert(), filas)
        total_insertados += len(filas)

    db.commit()
    return total_insertados


# ═════════════════════════════════════════════════════════════════════════════
# PIPELINE PRINCIPAL
# ═════════════════════════════════════════════════════════════════════════════

# Configuración de archivos de entrada y salida por año
ARCHIVOS: dict[int, dict] = {
    2017: {
        "entrada": ROOT / "data" / "personas_censo2017.csv",
        "salida":  ROOT / "data" / "censo_2017_aysen_final.csv",
        "extractor": extraer_2017,
    },
    2024: {
        "entrada": ROOT / "data" / "personas_censo2024.csv",
        "salida":  ROOT / "data" / "censo_2024_aysen_final.csv",
        "extractor": extraer_2024,
    },
}


def ejecutar_pipeline(anio: int, dry_run: bool = False) -> None:
    cfg = ARCHIVOS[anio]
    ruta_entrada: Path = cfg["entrada"]
    ruta_salida: Path  = cfg["salida"]

    print(f"\n{'─'*50}")
    print(f"  CENSO {anio}")
    print(f"{'─'*50}")

    # ── E ────────────────────────────────────────────────────────────────────
    print("\n  [E] Extracción")
    if not ruta_entrada.exists():
        print(f"    ⚠️  Archivo no encontrado: {ruta_entrada}")
        print(f"    Descarga el CSV desde https://www.ine.gob.cl y "
              f"colócalo en data/ como '{ruta_entrada.name}'")
        return

    df_crudo = cfg["extractor"](ruta_entrada)

    # ── T ────────────────────────────────────────────────────────────────────
    print("\n  [T] Transformación")
    df_limpio = transformar(df_crudo, anio)

    # Exportar CSV transformado (igual que hacía el notebook)
    df_limpio.to_csv(ruta_salida, index=False)
    print(f"    CSV transformado guardado: {ruta_salida.name}")

    if dry_run:
        print("\n  [L] Carga omitida (--dry-run activo).")
        return

    # ── L ────────────────────────────────────────────────────────────────────
    print("\n  [L] Carga en PostgreSQL")
    db = SessionLocal()
    try:
        _cargar_comunas(db)

        print(f"    Cargando indicadores demográficos ...", end=" ", flush=True)
        n = _cargar_indicadores(df_limpio, anio, db)
        print(f"✅ {n:,} nuevos registros insertados.")

    except Exception as exc:
        db.rollback()
        print(f"\n    ❌ Error durante la carga: {exc}")
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ETL pipeline — Monitoreo Demográfico Aysén (RF1)."
    )
    parser.add_argument(
        "--anio", type=int, choices=[2017, 2024], action="append",
        help="Año(s) a procesar. Sin este flag se procesan 2017 y 2024.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Ejecuta E+T pero omite la carga en PostgreSQL.",
    )
    args = parser.parse_args()

    anios = args.anio if args.anio else [2017, 2024]

    print("═" * 50)
    print("  ETL Pipeline — Monitoreo Demográfico Aysén")
    print("═" * 50)

    # Asegurar que las tablas existen antes de insertar
    if not args.dry_run:
        Base.metadata.create_all(bind=engine)
        print("\n  Tablas verificadas/creadas en PostgreSQL.")

    for anio in anios:
        ejecutar_pipeline(anio, dry_run=args.dry_run)

    print(f"\n{'═'*50}")
    print("  Pipeline completado.")
    print(f"{'═'*50}\n")


if __name__ == "__main__":
    main()