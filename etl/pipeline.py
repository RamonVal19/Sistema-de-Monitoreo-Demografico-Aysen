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
import zipfile
import requests
import subprocess
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

FUENTES: dict[int, dict] = {
    2024: {
    "url": "https://storage.googleapis.com/bktdescargascenso2024/personas_censo2024.zip",
    "zip": ROOT / "data" / "personas_censo2024.zip",
    "csv": ROOT / "data" / "personas_censo2024.csv",
    "nombre_csv_en_zip": "personas_censo2024.csv",
        },
    2017: {
    "url": "https://www.ine.gob.cl/docs/default-source/censo-de-poblacion-y-vivienda/bbdd/censo-2017/csv/csv-personas-censo-2017.rar?sfvrsn=60c6e91c_2&download=true",
    "rar_externo": ROOT / "data" / "personas_censo2017.rar",
    "rar_interno": ROOT / "data" / "microdato_censo2017-personas.rar",
    "csv": ROOT / "data" / "Microdato_Censo2017-Personas.csv",
    "nombre_rar_en_rar": "microdato_censo2017-personas.rar",
    "nombre_csv_en_rar": "Microdato_Censo2017-Personas.csv",
    },
}


def descargar_censo(anio: int) -> None:
    """
    Descarga y prepara el CSV del INE para el año indicado.
    Lógica:
      2024 — descarga ZIP desde Google Cloud Storage, extrae CSV.
      2017 — opción C: usa RAR local si existe, si no descarga desde URL INE.
              Luego extrae estructura RAR anidada → CSV.
    Si el CSV ya existe en data/, omite todo el proceso.
    """
    if anio not in FUENTES:
        return

    fuente = FUENTES[anio]
    csv_path: Path = fuente["csv"]

    if csv_path.exists():
        print(f"    CSV ya existe: {csv_path.name} — omitiendo descarga.")
        return

    # ── CENSO 2017 (RAR anidado) ──────────────────────────────────────────────
    if anio == 2017:
        rar_interno: Path = fuente["rar_interno"]
        rar_externo: Path = fuente["rar_externo"]

        if not rar_interno.exists() and not rar_externo.exists():
            print(f"    No se encontró RAR local — descargando desde URL del INE ...")
            url = fuente["url"]
            try:
                with requests.get(url, stream=True, timeout=600) as resp:
                    resp.raise_for_status()
                    total = int(resp.headers.get("content-length", 0))
                    descargado = 0
                    with open(rar_externo, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=1024 * 1024):
                            f.write(chunk)
                            descargado += len(chunk)
                            if total:
                                # Calcula % de descarga
                                pct = descargado / total * 100
                                print(
                                    f"      {pct:.1f}% "
                                    f"({descargado // 1024 // 1024} MB / "
                                    f"{total // 1024 // 1024} MB)",
                                    end="\r"
                                )
                print(f"\n    Descarga completa: {rar_externo.name}")
            except requests.RequestException as exc:
                raise RuntimeError(f"Error al descargar CENSO 2017: {exc}") from exc
        # Si el RAR ya está instalado localmente, no lo vuelve a descargar
        else:
            origen = rar_interno.name if rar_interno.exists() else rar_externo.name
            print(f"    RAR local encontrado: {origen} — omitiendo descarga.")

        _extraer_rar_anidado(fuente)
        return

    # ── CENSO 2024 (ZIP) ──────────────────────────────────────────────────────
    zip_path: Path = fuente["zip"]
    url: str = fuente["url"]

    print(f"    Descargando {url} ...")
    try:
        with requests.get(url, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            descargado = 0
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    descargado += len(chunk)
                    if total:
                        pct = descargado / total * 100
                        print(
                            f"      {pct:.1f}% "
                            f"({descargado // 1024 // 1024} MB / "
                            f"{total // 1024 // 1024} MB)",
                            end="\r"
                        )
        print(f"\n    Descarga completa: {zip_path.name}")
    except requests.RequestException as exc:
        raise RuntimeError(f"Error al descargar CENSO {anio}: {exc}") from exc

    print(f"    Extrayendo {zip_path.name} ...")
    nombre_csv = fuente["nombre_csv_en_zip"]
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            nombres = zf.namelist()
            match = next((n for n in nombres if n.endswith(nombre_csv)), None)
            if match is None:
                raise RuntimeError(
                    f"No se encontró '{nombre_csv}' en el ZIP. "
                    f"Archivos disponibles: {nombres}"
                )
            with zf.open(match) as origen, open(csv_path, "wb") as destino:
                destino.write(origen.read())
        print(f"    CSV extraído: {csv_path.name}")
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f"ZIP corrupto o incompleto: {exc}") from exc
    finally:
        if zip_path.exists():
            zip_path.unlink()
            print(f"    ZIP eliminado para ahorrar espacio.")

def _extraer_rar_anidado(fuente: dict) -> None:
    """
    Extrae CSV desde RAR anidado:
    personas_censo2017.rar → microdato_censo2017-personas.rar → CSV
    """
    rar_externo: Path = fuente["rar_externo"]
    rar_interno: Path = fuente["rar_interno"]
    csv_path: Path    = fuente["csv"]

    # Paso 1: extraer RAR interno desde RAR externo (si no existe ya)
    if not rar_interno.exists():
        if not rar_externo.exists():
            raise RuntimeError(
                f"No se encontró el RAR: {rar_externo.name}\n"
                f"Descárgalo desde:\n"
                f"  {fuente['url']}\n"
                f"y colócalo en data/ como '{rar_externo.name}'"
            )
        print(f"    Extrayendo {fuente['nombre_rar_en_rar']} del RAR externo ...")
        resultado = subprocess.run(
            ["unrar", "e", str(rar_externo),
             fuente["nombre_rar_en_rar"], str(ROOT / "data") + "/"],
            capture_output=True, text=True
        )
        if resultado.returncode != 0:
            raise RuntimeError(f"Error al extraer RAR interno: {resultado.stderr}")
        print(f"    RAR interno extraído: {fuente['nombre_rar_en_rar']}")
    else:
        print(f"    RAR interno ya existe: {rar_interno.name}")
    # Paso 2: extraer CSV desde RAR interno
    print(f"    Extrayendo {fuente['nombre_csv_en_rar']} del RAR interno ...")
    resultado = subprocess.run(
        ["unrar", "e", str(rar_interno),
         fuente["nombre_csv_en_rar"], str(ROOT / "data") + "/"],
        capture_output=True, text=True
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"Error al extraer CSV: {resultado.stderr}")
    print(f"    CSV extraído: {csv_path.name}")

    # Limpiar RARs para ahorrar espacio
    for rar in [rar_externo, rar_interno]:
        if rar.exists():
            rar.unlink()
    print(f"    RARs eliminados para ahorrar espacio.")

    # Limpiar archivos de etiquetas y documentación extraídos junto al CSV
    data_dir = ROOT / "data"
    for archivo in data_dir.iterdir():
        if archivo.name.startswith("etiquetas_") or archivo.suffix == ".pdf":
            archivo.unlink()
            print(f"    Eliminado: {archivo.name}")









# ═════════════════════════════════════════════════════════════════════════════
# E — EXTRACCIÓN
# ═════════════════════════════════════════════════════════════════════════════
def extraer_2017(ruta: Path) -> pd.DataFrame:
    """
    Carga el CSV 2017 nacional (separador punto y coma) en chunks.
    Solo lee las columnas necesarias y filtra por región 11.
    Columnas originales: REGION, COMUNA, P08 (sexo), P09 (edad)
    """
    cols = ["REGION", "COMUNA", "P08", "P09"]
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
        aysen = chunk[chunk["REGION"] == REGION_AYSEN]
        if not aysen.empty:
            bloques.append(aysen)
        if i % 10 == 0:
            print(f"      chunk {i} procesado ...")

    df = pd.concat(bloques, ignore_index=True)

    # Renombrar al formato estándar del pipeline
    df = df.rename(columns={
        "REGION": "region",
        "COMUNA": "comuna",
        "P08":    "sexo",
        "P09":    "edad",
    })

    print(f"    Registros región 11 encontrados: {len(df):,}")
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
    # edad_quinquenal es opcional — se calcula en transformar() si no existe
    cols_requeridas = COLS_REQUERIDAS - {"edad_quinquenal"}
    faltantes = cols_requeridas - set(df.columns)
    if faltantes:
        raise ValueError(
            f"'{nombre_archivo}' no tiene las columnas requeridas: {faltantes}"
        )

def transformar(df: pd.DataFrame, anio: int) -> pd.DataFrame:
    """
    Aplica todas las transformaciones de limpieza y normalización.

    Decisiones de limpieza documentadas:
      - Edades reservadas (valor -66 del INE) → NULL (pd.NA)
        Razón: -66 no es un dato demográfico real, NULL permite filtrarlos
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
    if "edad_quinquenal" in resultado.columns:
        resultado["edad_quinquenal"] = resultado["edad_quinquenal"].astype(int)

    # ── 3. edad_quinquenal: calcular si no viene en el CSV (CENSO 2017) ──────────
    if "edad_quinquenal" not in resultado.columns:
        edad_num = pd.to_numeric(resultado["edad"], errors="coerce")
        resultado["edad_quinquenal"] = (
        (edad_num // 5 * 5).clip(upper=85)
        .astype("Int64")  # nullable integer — acepta pd.NA
    )

    # ── 4. Edad: reservada → NULL ─────────────────────────────────────────────
    edad_numerica = pd.to_numeric(resultado["edad"], errors="coerce")
    resultado["edad"] = edad_numerica.where(edad_numerica != EDAD_RESERVADA, other=pd.NA)
    # Convertir a Int64 (nullable integer) para soportar pd.NA
    resultado["edad"] = resultado["edad"].astype("Int64")

    # ── 5. Mapeo de etiquetas ─────────────────────────────────────────────────
    resultado["nombre_comuna"] = resultado["comuna"].map(COMUNAS_AYSEN)
    resultado["sexo_label"] = resultado["sexo"].map(SEXO_LABEL)

    # ── 6. Control de calidad ─────────────────────────────────────────────────
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
        "entrada": ROOT / "data" / "Microdato_Censo2017-Personas.csv",
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

    # ── D — Descarga ──────────────────────────────────────────────────
    print("\n  [D] Descarga")
    descargar_censo(anio)
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