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
| ETL (extracción y transformación de datos) | Python / Pandas | ✅ Implementado |
| API REST | FastAPI + PostgreSQL + SQLAlchemy | ✅ Implementado |
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
Sistema-de-Monitoreo-Demografico-Aysen/
│
├── data/                              # Archivos CSV (ignorados por .gitignore)
│   ├── personas_censo2017.csv         # CSV INE Aysén 2017
│   ├── personas_censo2024.csv         # CSV INE nacional 2024
│   └── censo_2024_aysen_final.csv     # Generado por el pipeline ETL
│
├── etl/
│   ├── etl_censo_aysen.ipynb          # Notebook ETL exploratorio
│   └── pipeline.py                    # Pipeline ETL ejecutable (RF1)
│
├── api/
│   ├── main.py                        # Aplicación FastAPI
│   ├── database.py                    # Configuración SQLAlchemy
│   ├── models.py                      # Modelos ORM (tablas PostgreSQL)
│   ├── schemas.py                     # Schemas Pydantic (respuestas API)
│   └── routers/
│       ├── comunas.py                 # GET /comunas
│       └── indicadores.py             # GET /indicadores
│
├── scripts/
│   └── init_db.py                     # Crea las tablas en PostgreSQL
│
├── tests/
│   └── test_api.py                    # 28 tests (pytest + SQLite en memoria)
│
├── .env                               # Variables de entorno (no incluido en git)
├── .gitignore
├── requirements.txt
├── Procfile                           # Para despliegue en Railway
└── README.md
```

---

## Instalación y uso local

### 1. Clonar el repositorio

```bash
git clone https://github.com/RamonVal19/Sistema-de-Monitoreo-Demografico-Aysen.git
cd Sistema-de-Monitoreo-Demografico-Aysen
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
source venv/bin/activate       # Linux / macOS
# venv\Scripts\activate        # Windows

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto (nunca lo subas al repositorio):

```env
DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/monitoreo_demografico
```

### 4. Descargar los datos del INE

Descarga los archivos desde el sitio oficial del INE y colócalos en la carpeta `data/`:

- `personas_censo2017.csv` — base Aysén 2017
- `personas_censo2024.csv` — base nacional 2024

### 5. Inicializar la base de datos

```bash
PYTHONPATH=. python scripts/init_db.py
```

Esto crea las tablas `comunas` e `indicadores_demograficos` en PostgreSQL.

### 6. Ejecutar el pipeline ETL

```bash
# Procesar y cargar ambos años
PYTHONPATH=. python etl/pipeline.py

# Solo un año
PYTHONPATH=. python etl/pipeline.py --anio 2024

# Verificar transformación sin cargar en BD
PYTHONPATH=. python etl/pipeline.py --anio 2024 --dry-run
```

El pipeline ejecuta tres etapas:

- **E — Extracción:** lee los CSV del INE. El archivo 2024 (nacional) se procesa en chunks de 100.000 filas y se filtra por región 11.
- **T — Transformación:** limpia tipos, mapea etiquetas de comunas y sexo, convierte edades reservadas (código `-66` del INE) a `NULL`.
- **L — Carga:** inserta los registros en PostgreSQL e idempotente sobre el catálogo de comunas.

### 7. Levantar la API

```bash
PYTHONPATH=. uvicorn api.main:app --reload
```

La documentación interactiva estará disponible en `http://localhost:8000/docs`.

### 8. Correr los tests

```bash
PYTHONPATH=. pytest tests/test_api.py -v
```

Los tests usan SQLite en memoria y no requieren PostgreSQL ni los archivos CSV del INE.

---

## Endpoints disponibles

### Estado

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/` | Estado del servicio |
| GET | `/health` | Health check para Railway |

### Comunas

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/comunas/` | Listado de las 10 comunas de Aysén |
| GET | `/comunas/{codigo_comuna}` | Detalle de una comuna por código INE |

### Indicadores demográficos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/indicadores/sexo-edad/{codigo_comuna}` | Distribución por sexo y grupo etario quinquenal |
| GET | `/indicadores/envejecimiento/{codigo_comuna}` | Índice de envejecimiento de una comuna |
| GET | `/indicadores/envejecimiento` | Índice de envejecimiento de todas las comunas |

Todos los endpoints de indicadores aceptan el parámetro `?anio=2024` (por defecto) o `?anio=2017`.

**Ejemplo de respuesta** — `GET /indicadores/envejecimiento?anio=2024`:

```json
[
  {
    "codigo_comuna": 11101,
    "nombre_comuna": "Coyhaique",
    "anio_censo": 2024,
    "pob_65_mas": 7192,
    "pob_0_14": 11220,
    "indice_envejecimiento": 64.1
  },
  ...
]
```

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