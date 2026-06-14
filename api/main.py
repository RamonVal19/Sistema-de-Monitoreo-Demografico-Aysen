"""
API REST — Sistema de Monitoreo Demográfico Comunal de Aysén
Sprint 7 / OE2: endpoints de datos activos.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from api.routers import comunas, indicadores, admin

app = FastAPI(
    title="Sistema de Monitoreo Demográfico Comunal de Aysén",
    description=(
        "API REST para datos demográficos de las 10 comunas de Aysén "
        "(CENSO INE 2017 y 2024). Desarrollado por Ramón Valenzuela — "
        "Universidad de Aysén, TADS."
    ),
    version="0.2.0",
)

# CORS abierto para desarrollo; restringir en producción si el dashboard
# se despliega en un dominio específico.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(comunas.router)
app.include_router(indicadores.router)
app.include_router(admin.router)

# ── Endpoints de estado ───────────────────────────────────────────────────────

@app.get("/", tags=["Estado"])
def root():
    """Endpoint raíz — verifica que el servicio está en línea."""
    return {
        "estado": "activo",
        "proyecto": "Monitoreo Demográfico Aysén",
        "version": "0.2.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Estado"])
def health_check():
    """Health check para Railway."""
    return {"status": "ok"}

# ── Integración Dashboard Dash ────────────────────────────────────────────────
import sys
import os

# Establecer DASH_PREFIX antes de importar dashboard
if not os.getenv("DASH_PREFIX"):
    os.environ["DASH_PREFIX"] = "/dashboard/"

from a2wsgi import WSGIMiddleware
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dashboard.app import app as dash_app

app.mount("/dashboard", WSGIMiddleware(dash_app.server))