"""
API REST — Sistema de Monitoreo Demográfico Comunal de Aysén
Versión mínima para despliegue temprano en Railway (Sprint 5).
Los endpoints de datos se implementarán en Sprint 7 (OE2).
"""

from fastapi import FastAPI

app = FastAPI(
    title="Sistema de Monitoreo Demográfico Comunal de Aysén",
    description="API REST para datos demográficos de las 10 comunas de Aysén (CENSO 2017 y 2024)",
    version="0.1.0",
)


@app.get("/", tags=["Estado"])
def root():
    """Endpoint raíz — verifica que el servicio está en línea."""
    return {
        "estado": "activo",
        "proyecto": "Monitoreo Demográfico Aysén",
        "version": "0.1.0",
        "nota": "ETL implementado. Endpoints de datos disponibles en Sprint 7."
    }


@app.get("/health", tags=["Estado"])
def health_check():
    """Health check para Railway."""
    return {"status": "ok"}
