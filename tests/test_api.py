"""
Tests básicos para la API FastAPI.
Ejecutar con: pytest tests/
"""

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_root_retorna_200():
    response = client.get("/")
    assert response.status_code == 200


def test_root_contiene_estado():
    response = client.get("/")
    data = response.json()
    assert data["estado"] == "activo"


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
