# Sistema de Monitoreo Demográfico Comunal de Aysén

Sistema web de tres capas para el análisis y visualización de datos demográficos de las 10 comunas de la Región de Aysén, basado en los datos del CENSO INE 2017 y 2024.

**Desarrollado por:** Ramón Valenzuela  
**Institución:** Universidad de Aysén — Ingeniería Civil Informática  
**Asignatura:** Taller Avanzado de Desarrollo de Software (TADS)  
**Docente:** Gabriel Núñez

---

## Descripción

El proyecto permite a tesistas y estudiantes de la Universidad de Aysén explorar indicadores demográficos comunales sin necesidad de procesar los archivos CSV crudos del INE. La arquitectura consta de tres componentes:

| Capa | Tecnología | Estado |
|------|-----------|--------|
| ETL (extracción y transformación de datos) | Python / Pandas / GeoPandas | ✅ En desarrollo |
| API REST | FastAPI + PostgreSQL | 🔄 Planificado S7 |
| Dashboard interactivo | Dash + Plotly | 🔄 Condicional a OE1/OE2 |

## Indicadores implementados

- Distribución de población por sexo y grupo etario quinquenal
- Índice de envejecimiento por comuna `(pob. 65+) / (pob. 0–14) × 100`

## Fuentes de datos

- [INE — CENSO 2017](https://www.ine.gob.cl/estadisticas/sociales/censos-de-poblacion-y-vivienda/censo-de-poblacion-y-vivienda)
- [INE — CENSO 2024](https://www.ine.gob.cl/estadisticas/sociales/censos-de-poblacion-y-vivienda/censo-de-poblacion-y-vivienda)

> Los archivos CSV del INE **no se incluyen en este repositorio** por su tamaño. Ver instrucciones de descarga más abajo.

---

## Estructura del proyecto

```
sistema_monitoreo_demografico/
│
├── data/                          # Archivos CSV (ignorados por .gitignore)
│   ├── personas_censo2017.csv     # CSV INE Aysén 2017
│   ├── personas_censo2024.csv     # CSV INE nacional 2024
│   └── censo_2024_aysen_final.csv # Generado por el ETL
│
├── etl/
│   └── etl_censo_aysen.ipynb     # Notebook ETL principal
│
├── api/                           # FastAPI (Sprint 7)
│   └── main.py
│
├── dashboard/                     # Dash + Plotly (condicional)
│   └── app.py
│
├── tests/                         # pytest + TestClient
│   └── test_api.py
│
├── docs/                          # Documentación adicional
│
├── .gitignore
├── requirements.txt
├── Procfile                       # Para despliegue en Railway
└── README.md
```

---

## Instalación y uso local

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/sistema_monitoreo_demografico.git
cd sistema_monitoreo_demografico
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
source venv/bin/activate       # Linux / macOS
# venv\Scripts\activate        # Windows

pip install -r requirements.txt
```

### 3. Descargar los datos del INE

Descarga los archivos desde el sitio oficial del INE y colócalos en la carpeta `data/`:
- `personas_censo2017.csv` — base Aysén 2017
- `personas_censo2024.csv` — base nacional 2024

### 4. Ejecutar el ETL

```bash
jupyter notebook etl/etl_censo_aysen.ipynb
```

Ejecutar todas las celdas en orden. Los archivos procesados se guardarán en `data/`.

---

## Despliegue en Railway

El proyecto está configurado para desplegarse en [Railway](https://railway.app).

1. Conectar el repositorio GitHub a Railway
2. Agregar las variables de entorno desde el panel de Railway:
   ```
   DATABASE_URL=postgresql://...
   ```
3. Railway detectará el `Procfile` automáticamente

---

## Variables de entorno

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `DATABASE_URL` | URL de conexión PostgreSQL | `postgresql://user:pass@host:5432/db` |

Crea un archivo `.env` local (nunca lo subas al repositorio):

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/monitoreo_demografico
```
