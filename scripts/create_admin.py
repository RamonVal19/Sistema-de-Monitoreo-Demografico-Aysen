"""
Script para crear un usuario administrador en la BD.

Uso:
    PYTHONPATH=. python scripts/create_admin.py
"""

import sys
from pathlib import Path

# sys.path.insert(0, ...): agrega el directorio raíz del proyecto al path de Python
# para que los imports relativos (from api.database import...) funcionen correctamente
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.database import SessionLocal, engine, Base
from api.auth import hash_password
import api.models  # noqa: F401 — necesario para que SQLAlchemy registre los modelos
from api.models import Usuario


def main():
    # Crea todas las tablas si no existen (idempotente)
    Base.metadata.create_all(bind=engine)

    username  = input("Username: ").strip()
    email     = input("Email: ").strip()
    password  = input("Password: ").strip()

    if len(password) < 8:
        print("❌ La contraseña debe tener al menos 8 caracteres.")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Valida que no exista usuario con ese username O email (| = OR lógico)
        existe = db.query(Usuario).filter(
            (Usuario.username == username) | (Usuario.email == email)
        ).first()
        if existe:
            print(f"❌ Ya existe un usuario con ese username o email.")
            sys.exit(1)

        usuario = Usuario(
            username=username,
            email=email,
            hashed_password=hash_password(password),  # Hash bcrypt irreversible
            is_active=True,
        )
        db.add(usuario)
        db.commit()
        print(f"✅ Usuario '{username}' creado correctamente.")
    finally:
        # Cierra la sesión incluso si ocurre una excepción
        db.close()


if __name__ == "__main__":
    main()