"""
api/routers/admin.py
────────────────────
Endpoints del panel administrativo — todos protegidos con JWT.

Endpoints:
  POST /admin/login              — autenticación, retorna JWT
  GET  /admin/estado-bd          — conteo de registros por año y comuna
  POST /admin/ejecutar-etl       — dispara el pipeline ETL en background
  GET  /admin/etl-status         — estado del último ETL ejecutado
"""

import subprocess  # Para ejecutar scripts Python en subprocesos separados
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm  # Form-data para login (username+password)
from pydantic import BaseModel
from pydantic import field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.auth import (
    create_access_token,
    get_current_user,
    verify_password,
)
from api.database import get_db
from api.models import Comuna, IndicadorDemografico, Usuario

router = APIRouter(prefix="/admin", tags=["Administración"])

# Estado en memoria del último ETL ejecutado
# (En producción usar Redis o BD para persistencia entre reinicio del servidor)
_etl_estado: dict = {
    "en_curso": False,
    "ultimo_inicio": None,
    "ultimo_fin": None,
    "ultimo_resultado": None,  # "exitoso" | "error"
    "ultimo_mensaje": None,
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class TokenOut(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    username:     str


class EstadoBDOut(BaseModel):
    total_registros: int
    por_anio: list[dict]
    por_comuna: list[dict]

# Validar año
class ETLRequest(BaseModel):
    anio: Optional[int] = None

    @field_validator("anio")
    @classmethod
    def validar_anio(cls, v):
        if v is not None and v not in (2017, 2024):
            raise ValueError("El año debe ser 2017, 2024 o null (ambos).")
        return v


class ETLStatusOut(BaseModel):
    en_curso:        bool
    ultimo_inicio:   Optional[str]
    ultimo_fin:      Optional[str]
    ultimo_resultado: Optional[str]
    ultimo_mensaje:  Optional[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenOut,
    summary="Iniciar sesión como administrador",
)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Autentica al administrador y retorna un JWT.
    
    OAuth2PasswordRequestForm: interpreta form-data (username + password)
    en lugar de JSON, compatible con Swagger.
    """
    usuario = db.query(Usuario).filter(
        Usuario.username == form.username,
        Usuario.is_active == True,
    ).first()

    if not usuario or not verify_password(form.password, usuario.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": usuario.username})
    return TokenOut(access_token=token, username=usuario.username)


@router.get(
    "/estado-bd",
    response_model=EstadoBDOut,
    summary="Estado de la base de datos",
)
def estado_bd(
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    """
    Retorna conteo de registros por año de censo y por comuna.
    
    El parámetro _ (usuario) valida el JWT pero no se usa en el endpoint.
    Su presencia es suficiente para proteger la ruta (Depends ejecuta la validación).
    """
    total = db.query(func.count(IndicadorDemografico.id)).scalar() or 0

    por_anio = [
        {"anio_censo": anio, "cantidad": cantidad}
        for anio, cantidad in db.query(
            IndicadorDemografico.anio_censo,
            func.count(IndicadorDemografico.id),
        ).group_by(IndicadorDemografico.anio_censo).order_by(
            IndicadorDemografico.anio_censo
        ).all()
    ]

    por_comuna = [
        {"codigo_comuna": cod, "nombre_comuna": nombre, "cantidad": cantidad}
        for cod, nombre, cantidad in db.query(
            IndicadorDemografico.codigo_comuna,
            Comuna.nombre_comuna,
            func.count(IndicadorDemografico.id),
        ).join(Comuna, IndicadorDemografico.codigo_comuna == Comuna.codigo_comuna)
        .group_by(IndicadorDemografico.codigo_comuna, Comuna.nombre_comuna)
        .order_by(IndicadorDemografico.codigo_comuna)
        .all()
    ]

    return EstadoBDOut(
        total_registros=total,
        por_anio=por_anio,
        por_comuna=por_comuna,
    )


@router.post(
    "/ejecutar-etl",
    summary="Ejecutar pipeline ETL manualmente",
)
def ejecutar_etl(
    request: ETLRequest,
    _: Usuario = Depends(get_current_user),
):
    """
    Dispara el pipeline ETL en un subproceso separado sin bloquear.
    
    Flujo:
      1. Valida que no haya un ETL en curso (si lo hay, retorna 409)
      2. Construye comando: python etl/pipeline.py [--anio XXXX]
      3. Ejecuta en subprocess con timeout de 1 hora
      4. Captura stdout/stderr y actualiza _etl_estado
      5. Retorna inmediatamente al cliente (ETL sigue en background)
    
    Nota: _etl_estado se pierde si reinicia el servidor; usar Redis en producción.
    """
    if _etl_estado["en_curso"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya hay un pipeline ETL en ejecución.",
        )

    # Construir ruta absoluta al script ETL
    # Path(__file__) = /ruta/a/api/routers/admin.py
    # .resolve().parent.parent.parent = /ruta/a/ (sube 3 niveles)
    pipeline = Path(__file__).resolve().parent.parent.parent / "etl" / "pipeline.py"
    cmd = [sys.executable, str(pipeline)]
    if request.anio:
        cmd += ["--anio", str(request.anio)]

    # En Railway los CSVs no están disponibles — omitir descarga
    if os.getenv("RAILWAY_ENVIRONMENT"):
        cmd += ["--skip-download"]

    # Actualizar estado: marca como "en curso"
    _etl_estado["en_curso"]      = True
    _etl_estado["ultimo_inicio"] = datetime.now(timezone.utc).isoformat()
    _etl_estado["ultimo_fin"]    = None
    _etl_estado["ultimo_resultado"] = None
    _etl_estado["ultimo_mensaje"]   = None

    try:
        # subprocess.run: ejecuta comando y espera a que termine
        # capture_output=True: captura stdout/stderr
        # text=True: retorna strings en lugar de bytes
        # timeout=3600: máximo 1 hora de ejecución
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
        )
        _etl_estado["ultimo_resultado"] = "exitoso" if result.returncode == 0 else "error"
        # Guarda últimas 500 caracteres del log (evita respuestas enormes)
        _etl_estado["ultimo_mensaje"]   = result.stdout[-500:] if result.stdout else result.stderr[-500:]
    except subprocess.TimeoutExpired:
        _etl_estado["ultimo_resultado"] = "error"
        _etl_estado["ultimo_mensaje"]   = "El pipeline superó el tiempo máximo de 1 hora."
    except Exception as exc:
        _etl_estado["ultimo_resultado"] = "error"
        _etl_estado["ultimo_mensaje"]   = str(exc)
    finally:
        # Siempre ejecutado, incluso si hay excepción
        _etl_estado["en_curso"]   = False
        _etl_estado["ultimo_fin"] = datetime.now(timezone.utc).isoformat()

    if _etl_estado["ultimo_resultado"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_etl_estado["ultimo_mensaje"],
        )

    return {
        "resultado": _etl_estado["ultimo_resultado"],
        "inicio":    _etl_estado["ultimo_inicio"],
        "fin":       _etl_estado["ultimo_fin"],
        "log":       _etl_estado["ultimo_mensaje"],
    }


@router.get(
    "/etl-status",
    response_model=ETLStatusOut,
    summary="Estado del último ETL ejecutado",
)
def etl_status(_: Usuario = Depends(get_current_user)):
    """
    Retorna el estado actual o del último pipeline ETL ejecutado.
    
    ** desempaqueta _etl_estado (dict) en argumentos nombrados de ETLStatusOut.
    """
    return ETLStatusOut(**_etl_estado)