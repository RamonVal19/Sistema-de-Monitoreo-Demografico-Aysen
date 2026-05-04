"""
Configuración de la conexión a PostgreSQL mediante SQLAlchemy.
La URL se lee desde la variable de entorno DATABASE_URL (Railway / .env local).
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    raise RuntimeError("La variable de entorno DATABASE_URL no está definida.")

# Railway a veces entrega URLs con prefijo 'postgres://' (psycopg2 requiere 'postgresql://')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

#engine es el "cable" que une python con PostgreSQL
engine = create_engine(DATABASE_URL, echo=False)

#crea una sesión que acumula operaciones y las envía juntas.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Clase base para todos los modelos ORM del proyecto."""
    pass


# get_db es el proveedor de sesiones para FastAPI: Utiliza un generado que FastAPI llama antes de cada request, entrega la sesión al endpoint, y cuando el request termina garantiza que ninguna conexión quede abierta.
def get_db():
    """
    Dependencia de FastAPI que provee una sesión de BD por request
    y garantiza su cierre al terminar.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()