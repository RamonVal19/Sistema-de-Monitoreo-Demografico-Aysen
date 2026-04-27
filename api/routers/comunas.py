"""
Router: /comunas
Expone el catálogo de las 10 comunas de la región de Aysén.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Comuna
from api.schemas import ComunaOut

router = APIRouter(prefix="/comunas", tags=["Comunas"])


@router.get("/", response_model=list[ComunaOut], summary="Listado de comunas")
def listar_comunas(db: Session = Depends(get_db)):
    """
    Devuelve todas las comunas disponibles en la base de datos,
    ordenadas por código comunal INE.
    """
    return db.query(Comuna).order_by(Comuna.codigo_comuna).all()


@router.get(
    "/{codigo_comuna}",
    response_model=ComunaOut,
    summary="Detalle de una comuna",
)
def obtener_comuna(codigo_comuna: int, db: Session = Depends(get_db)):
    """
    Devuelve una sola comuna por su código INE (ej. 11201 → Aysén).
    Retorna 404 si no existe.
    """
    comuna = db.query(Comuna).filter(
        Comuna.codigo_comuna == codigo_comuna
    ).first()

    if comuna is None:
        raise HTTPException(
            status_code=404,
            detail=f"Comuna con código {codigo_comuna} no encontrada.",
        )
    return comuna