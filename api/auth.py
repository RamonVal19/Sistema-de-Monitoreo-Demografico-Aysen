"""
api/auth.py
───────────
Módulo de autenticación JWT para el panel administrativo.

Flujo:
  1. El admin hace POST /admin/login con username + password
  2. Se verifica el hash bcrypt contra la BD
  3. Si es válido, se retorna un JWT firmado con SECRET_KEY
  4. Los endpoints protegidos usan Depends(get_current_user) para validar el token
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

# FastAPI + OAuth2 para inyectar dependencias y esquema de seguridad
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# PyJWT para crear/validar tokens, y passlib para hash bcrypt de contraseñas
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Usuario

# ── Configuración ─────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esto-en-produccion")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# OAuth2PasswordBearer: registra /admin/login como endpoint de token en swagger
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")


# ── Hashing de contraseñas ────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Genera un hash bcrypt irreversible de la contraseña."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica una contraseña contra su hash bcrypt."""
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Crea un JWT firmado con expiración.
    
    El payload contiene el claim "sub" (subject) con el username.
    FastAPI automáticamente inyecta este token en el header Authorization.
    """
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    )
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decodifica y valida un JWT.
    
    Lanza JWTError si:
      - La firma es inválida (manipulado o diferente SECRET_KEY)
      - El token ha expirado (exp < now)
      - El formato no es válido
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── Dependencia FastAPI ───────────────────────────────────────────────────────

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Dependencia inyectable que valida el JWT y retorna el usuario activo.
    
    Usada en endpoints protegidos: @app.get("/admin/data", dependencies=[Depends(get_current_user)])
    o como parámetro: def endpoint(current_user: Usuario = Depends(get_current_user))
    
    Flujo:
      1. Extrae token del header Authorization (manejado por oauth2_scheme)
      2. Decodifica y obtiene username del claim "sub"
      3. Consulta BD y verifica que Usuario.is_active == True
      4. Retorna Usuario o lanza 401 Unauthorized
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    usuario = db.query(Usuario).filter(
        Usuario.username == username,
        Usuario.is_active == True,
    ).first()

    if usuario is None:
        raise credentials_exception

    return usuario