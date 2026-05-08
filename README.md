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
| ETL (extracción, transformación y carga) | Python / Pandas | ✅ Implementado |
| API REST | FastAPI + PostgreSQL + SQLAlchemy | ✅ Implementado |
| Dashboard interactivo | Dash + Plotly | 🔄 Condicional a OE1/OE2 |

## API en producción

La API está desplegada en Railway y accesible públicamente:

| Recurso | URL |
|---------|-----|
| API raíz | https://web-production-51433.up.railway.app |
| Documentación Swagger | https://web-production-51433.up.railway.app/docs |
| Índice de envejecimiento 2024 | https://web-production-51433.up.railway.app/indicadores/envejecimiento?anio=2024 |
| Índice de envejecimiento 2017 | https://web-production-51433.up.railway.app/indicadores/envejecimiento?anio=2017 |

## Indicadores implementados

- Distribución de población por sexo y grupo etario quinquenal
- Índice de envejecimiento por comuna `(pob. 65+) / (pob. 0–14) × 100`

Ambos indicadores están disponibles para comparación intercensal entre CENSO 2017 y CENSO 2024.

## Fuentes de datos

| Censo | Formato | Descarga |
|-------|---------|----------|
| CENSO 2024 | ZIP (338 MB) → CSV | ✅ Automática desde Google Cloud Storage |
| CENSO 2017 | RAR anidado (230 MB) → CSV | ✅ Automática desde URL INE o RAR local |

> Los archivos CSV del INE **no se incluyen en este repositorio** por su tamaño (>2 GB cada uno). El pipeline los descarga automáticamente al ejecutarse por primera vez.

---

## Estructura del proyecto

```
Sistema-de-Monitoreo-Demografico-Aysen/
│
├── data/                              # Archivos CSV (ignorados por .gitignore)
│   ├── Microdato_Censo2017-Personas.csv   # CSV INE 2017 (extraído por pipeline)
│   ├── personas_censo2024.csv             # CSV INE 2024 (descargado por pipeline)
│   ├── censo_2017_aysen_final.csv         # Output ETL 2017
│   └── censo_2024_aysen_final.csv         # Output ETL 2024
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

### 4. Inicializar la base de datos

```bash
PYTHONPATH=. python scripts/init_db.py
```

Esto crea las tablas `comunas` e `indicadores_demograficos` en PostgreSQL.

### 5. Ejecutar el pipeline ETL

El pipeline descarga, transforma y carga los datos automáticamente:

```bash
# Procesar y cargar ambos años (recomendado la primera vez)
PYTHONPATH=. python etl/pipeline.py

# Solo un año
PYTHONPATH=. python etl/pipeline.py --anio 2024
PYTHONPATH=. python etl/pipeline.py --anio 2017

# Verificar transformación sin cargar en BD
PYTHONPATH=. python etl/pipeline.py --anio 2024 --dry-run
```

El pipeline ejecuta cuatro etapas:

- **D — Descarga:** descarga automática desde las URLs oficiales del INE. Si el CSV ya existe en `data/`, omite la descarga. Para el 2017, usa el RAR local si está disponible antes de intentar la descarga remota.
- **E — Extracción:** lee los CSV en chunks de 100.000 filas y filtra por región 11 (Aysén). El CENSO 2017 usa separador `;` y columnas `P08`/`P09` que se renombran al formato estándar del pipeline.
- **T — Transformación:** limpia tipos, mapea etiquetas de comunas y sexo, convierte edades reservadas (código `-66` del INE) a `NULL`. Calcula `edad_quinquenal` para el 2017 mediante `min((edad // 5) * 5, 85)`.
- **L — Carga:** inserta los registros en PostgreSQL en lotes de 2.000 filas. El catálogo de comunas es idempotente.

### 6. Levantar la API

```bash
PYTHONPATH=. uvicorn api.main:app --reload
```

La documentación interactiva estará disponible en `http://localhost:8000/docs`.

### 7. Correr los tests

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

**Ejemplo — CENSO 2024:** `GET /indicadores/envejecimiento?anio=2024`

```json
[
  {
    "codigo_comuna": 11101,
    "nombre_comuna": "Coyhaique",
    "anio_censo": 2024,
    "pob_65_mas": 7192,
    "pob_0_14": 11220,
    "indice_envejecimiento": 64.1
  }
]
```

**Ejemplo — CENSO 2017:** `GET /indicadores/envejecimiento?anio=2017`

```json
[
  {
    "codigo_comuna": 11101,
    "nombre_comuna": "Coyhaique",
    "anio_censo": 2017,
    "pob_65_mas": 5148,
    "pob_0_14": 13471,
    "indice_envejecimiento": 38.22
  }
]
```

---

## Despliegue en Railway

El proyecto está desplegado en [Railway](https://railway.app) con CI/CD desde GitHub. Cada `git push` a `main` dispara un redeploy automático.

### Configuración desde cero

1. Crear proyecto en Railway y conectar el repositorio GitHub
2. Agregar un servicio PostgreSQL desde el panel de Railway
3. En el servicio de la API, configurar las variables de entorno:
   ```
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   PYTHONPATH=/app
   ```
4. Railway detectará el `Procfile` automáticamente
5. Una vez desplegado, inicializar la BD y cargar datos apuntando a la `DATABASE_PUBLIC_URL`:
   ```bash
   export DATABASE_URL=postgresql://...  # usar DATABASE_PUBLIC_URL de Railway
   PYTHONPATH=. python scripts/init_db.py
   PYTHONPATH=. python etl/pipeline.py
   ```

---

## Variables de entorno

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `DATABASE_URL` | URL de conexión PostgreSQL | `postgresql://user:pass@host:5432/db` |
| `PYTHONPATH` | Path para imports del paquete `api/` | `/app` (Railway) · `.` (local) |

---

## Datos en producción

| Métrica | Valor |
|---------|-------|
| Registros CENSO 2024 | 100.745 |
| Registros CENSO 2017 | 103.158 |
| Comunas cargadas | 10 |
| Edades reservadas → NULL (2024) | 19.752 |
| Endpoints disponibles | 5 |
| Tests automatizados | 28/28 ✅ |