#!/usr/bin/env python
# coding: utf-8

# # ETL — Sistema de Monitoreo Demográfico Comunal de Aysén
# 
# Este notebook implementa el proceso de Extracción, Transformación y Carga (ETL) de los datos del CENSO INE 2017 y 2024 para la Región de Aysén.
# 
# **Estructura del proceso:**
# 1. Extracción de datos crudos (CSV del INE)
# 2. Transformación: filtro por región, limpieza, normalización
# 3. Cálculo de indicadores demográficos
# 4. Exportación de archivos procesados (para carga posterior en PostgreSQL)
# 
# ---

# ## 0. Configuración e Imports

# In[1]:


import pandas as pd

# ── Rutas de archivos ──────────────────────────────────────────────────────────
RUTA_CENSO_2017 = 'data/personas_censo2017.csv'
RUTA_CENSO_2024 = 'data/personas_censo2024.csv'

RUTA_SALIDA_2024 = 'data/censo_2024_aysen_final.csv'

# ── Constantes del dominio ─────────────────────────────────────────────────────
REGION_AYSEN = 11

COMUNAS = {
    11101: 'Coyhaique',
    11102: 'Lago Verde',
    11201: 'Aysén',
    11202: 'Cisnes',
    11203: 'Guaitecas',
    11301: 'Cochrane',
    11302: "O'Higgins",
    11303: 'Tortel',
    11401: 'Chile Chico',
    11402: 'Río Ibáñez'
}

COLUMNAS_2024 = ['region', 'comuna', 'sexo', 'edad', 'edad_quinquenal']

print("Configuración lista.")


# ---
# ## 1. EXTRACCIÓN
# 
# ### 1.1 Extracción CENSO 2017
# 
# El archivo del 2017 ya es específico de Aysén, por lo que se carga directamente.

# In[2]:


df_aysen_2017 = pd.read_csv(RUTA_CENSO_2017, sep=',')

print(f"Registros CENSO 2017 cargados: {len(df_aysen_2017):,}")
print(f"Columnas: {df_aysen_2017.columns.tolist()}")
df_aysen_2017.head(3)


# ### 1.2 Extracción CENSO 2024 (procesamiento por chunks)
# 
# El archivo 2024 contiene datos de todo Chile. Se procesa en chunks para no saturar la memoria RAM y se filtra directamente por región 11.

# In[3]:


lista_aysen = []
lector = pd.read_csv(
    RUTA_CENSO_2024,
    sep=';',
    usecols=COLUMNAS_2024,
    chunksize=100_000,
    low_memory=False
)

for i, chunk in enumerate(lector):
    aysen_chunk = chunk[chunk['region'] == REGION_AYSEN]
    if not aysen_chunk.empty:
        lista_aysen.append(aysen_chunk)
    if i % 10 == 0:
        print(f"  Procesando chunk {i}...")

df_aysen_2024 = pd.concat(lista_aysen, ignore_index=True)

print(f"\n✓ Extracción completa.")
print(f"  Registros de Aysén encontrados: {len(df_aysen_2024):,}")


# ---
# ## 2. TRANSFORMACIÓN
# 
# ### 2.1 Limpieza y normalización de columnas

# In[4]:


# ── Limpieza de tipos ──────────────────────────────────────────────────────────
# Convertir 'edad' a numérico; valores inválidos se reemplazan por 0
df_aysen_2024['edad'] = (
    pd.to_numeric(df_aysen_2024['edad'], errors='coerce')
    .fillna(0)
    .astype(int)
)

# Asegurar que 'comuna' sea entero para el mapeo
df_aysen_2024['comuna'] = df_aysen_2024['comuna'].astype(int)

# ── Mapeo de etiquetas ─────────────────────────────────────────────────────────
df_aysen_2024['nombre_comuna'] = df_aysen_2024['comuna'].map(COMUNAS)
df_aysen_2024['sexo_label'] = df_aysen_2024['sexo'].map({1: 'Hombre', 2: 'Mujer'})

# ── Verificación de calidad ────────────────────────────────────────────────────
nulos_comuna = df_aysen_2024['nombre_comuna'].isna().sum()
nulos_sexo   = df_aysen_2024['sexo_label'].isna().sum()
print(f"Registros con nombre_comuna no mapeado: {nulos_comuna}")
print(f"Registros con sexo_label no mapeado:    {nulos_sexo}")

df_aysen_2024.head()


# ### 2.2 Indicador 1 — Distribución por sexo y grupo etario quinquenal

# In[5]:


indicador_sexo_edad = (
    df_aysen_2024
    .groupby(['nombre_comuna', 'edad_quinquenal', 'sexo_label'])
    .size()
    .reset_index(name='poblacion')
    .sort_values(['nombre_comuna', 'edad_quinquenal'])
)

print("=== Distribución por sexo y grupo etario (muestra: Chile Chico) ===")
print(indicador_sexo_edad[indicador_sexo_edad['nombre_comuna'] == 'Chile Chico'].to_string(index=False))


# ### 2.3 Indicador 2 — Índice de envejecimiento por comuna
# 
# **Fórmula:** `(población 65+) / (población 0–14) × 100`
# 
# Se usa `edad_quinquenal` en lugar de `edad` individual por ser la columna más confiable para toda la región (incluye Chile Chico).

# In[6]:


mayores = df_aysen_2024[df_aysen_2024['edad_quinquenal'] >= 65].groupby('nombre_comuna').size()
jovenes = df_aysen_2024[df_aysen_2024['edad_quinquenal'] <= 10].groupby('nombre_comuna').size()

indice_envejecimiento = pd.DataFrame({
    'pob_65_mas': mayores,
    'pob_0_14':   jovenes
}).fillna(0)

indice_envejecimiento['indice_envejecimiento'] = (
    (indice_envejecimiento['pob_65_mas'] / indice_envejecimiento['pob_0_14'] * 100)
    .round(1)
)

print("=== Índice de Envejecimiento por Comuna (CENSO 2024) ===")
print(indice_envejecimiento.sort_values('indice_envejecimiento', ascending=False).to_string())


# ---
# ## 3. CARGA (Exportación local)
# 
# Se exportan los datos procesados a CSV para su posterior carga en PostgreSQL (Sprint 7).

# In[7]:


# Datos base transformados
df_aysen_2024.to_csv(RUTA_SALIDA_2024, index=False)
print(f"✓ Datos base guardados en: {RUTA_SALIDA_2024}")

# Indicadores calculados
indicador_sexo_edad.to_csv('data/indicador_sexo_edad.csv', index=False)
indice_envejecimiento.to_csv('data/indice_envejecimiento.csv')
print("✓ Indicadores exportados.")
print("\n[Pendiente S7] Carga en PostgreSQL via SQLAlchemy + psycopg2")

