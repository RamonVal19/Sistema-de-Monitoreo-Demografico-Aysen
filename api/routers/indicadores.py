"""
Router: /indicadores
Endpoints de análisis demográfico: distribución sexo/edad e índice de envejecimiento.
Todos los cálculos ocurren en la base de datos vía SQLAlchemy, sin Pandas.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.database import get_db
from api.models import Comuna, IndicadorDemografico
from api.schemas import (
    DistribucionSexoEdadOut,
    GrupoEtarioItem,
    IndiceEnvejecimientoOut,
)

router = APIRouter(prefix="/indicadores", tags=["Indicadores"])

# ── Constantes ────────────────────────────────────────────────────────────────
ANIOS_VALIDOS = {2017, 2024}


def _validar_anio(anio: int) -> None:
    if anio not in ANIOS_VALIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"Año '{anio}' no válido. Use 2017 o 2024.",
        )


def _obtener_comuna_o_404(codigo_comuna: int, db: Session) -> Comuna:
    comuna = db.query(Comuna).filter(
        Comuna.codigo_comuna == codigo_comuna
    ).first()
    if comuna is None:
        raise HTTPException(
            status_code=404,
            detail=f"Comuna con código {codigo_comuna} no encontrada.",
        )
    return comuna


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/sexo-edad/{codigo_comuna}",
    response_model=DistribucionSexoEdadOut,
    summary="Distribución de población por sexo y grupo etario quinquenal",
)
def distribucion_sexo_edad(
    codigo_comuna: int,
    anio: int = Query(2024, description="Año del censo: 2017 o 2024"),
    db: Session = Depends(get_db),
):
    """
    Devuelve la cantidad de personas por grupo etario quinquenal y sexo
    para una comuna y año de censo determinados.

    - **codigo_comuna**: código INE de 5 dígitos (ej. 11201)
    - **anio**: año del censo (2017 o 2024)

    Los registros con edad negativa (persona que reservó su edad) se incluyen
    en el grupo quinquenal correspondiente asignado por el ETL.
    """
    _validar_anio(anio)
    comuna = _obtener_comuna_o_404(codigo_comuna, db)

    filas = (
        db.query(
            IndicadorDemografico.edad_quinquenal,
            IndicadorDemografico.sexo_label,
            func.count(IndicadorDemografico.id).label("cantidad"),
        )
        .filter(
            IndicadorDemografico.codigo_comuna == codigo_comuna,
            IndicadorDemografico.anio_censo == anio,
        )
        .group_by(
            IndicadorDemografico.edad_quinquenal,
            IndicadorDemografico.sexo_label,
        )
        .order_by(
            IndicadorDemografico.edad_quinquenal,
            IndicadorDemografico.sexo_label,
        )
        .all()
    )

    distribucion = [
        GrupoEtarioItem(
            edad_quinquenal=fila.edad_quinquenal,
            sexo_label=fila.sexo_label,
            cantidad=fila.cantidad,
        )
        for fila in filas
    ]

    return DistribucionSexoEdadOut(
        codigo_comuna=codigo_comuna,
        nombre_comuna=comuna.nombre_comuna,
        anio_censo=anio,
        distribucion=distribucion,
    )


@router.get(
    "/envejecimiento/{codigo_comuna}",
    response_model=IndiceEnvejecimientoOut,
    summary="Índice de envejecimiento de una comuna",
)
def indice_envejecimiento(
    codigo_comuna: int,
    anio: int = Query(2024, description="Año del censo: 2017 o 2024"),
    db: Session = Depends(get_db),
):
    """
    Calcula el índice de envejecimiento para una comuna y año:

        IE = (población 65+) / (población 0–14) × 100

    Un IE > 100 indica que hay más adultos mayores que niños/jóvenes.
    Retorna `null` si la población de 0–14 es cero (división no definida).
    """
    _validar_anio(anio)
    comuna = _obtener_comuna_o_404(codigo_comuna, db)

    base_query = db.query(func.count(IndicadorDemografico.id)).filter(
        IndicadorDemografico.codigo_comuna == codigo_comuna,
        IndicadorDemografico.anio_censo == anio,
    )

    pob_65_mas: int = base_query.filter(
        IndicadorDemografico.edad_quinquenal >= 65
    ).scalar() or 0

    pob_0_14: int = base_query.filter(
        IndicadorDemografico.edad_quinquenal <= 10  # grupos 0, 5, 10
    ).scalar() or 0

    if pob_0_14 == 0:
        indice = None
    else:
        indice = round((pob_65_mas / pob_0_14) * 100, 2)

    return IndiceEnvejecimientoOut(
        codigo_comuna=codigo_comuna,
        nombre_comuna=comuna.nombre_comuna,
        anio_censo=anio,
        pob_65_mas=pob_65_mas,
        pob_0_14=pob_0_14,
        indice_envejecimiento=indice,
    )


@router.get(
    "/envejecimiento",
    response_model=list[IndiceEnvejecimientoOut],
    summary="Índice de envejecimiento — todas las comunas",
)
def indice_envejecimiento_region(
    anio: int = Query(2024, description="Año del censo: 2017 o 2024"),
    db: Session = Depends(get_db),
):
    """
    Devuelve el índice de envejecimiento para **todas** las comunas de Aysén
    en un mismo año de censo. Útil para comparaciones regionales.
    """
    _validar_anio(anio)
    comunas = db.query(Comuna).order_by(Comuna.codigo_comuna).all()

    resultados = []
    for comuna in comunas:
        base = db.query(func.count(IndicadorDemografico.id)).filter(
            IndicadorDemografico.codigo_comuna == comuna.codigo_comuna,
            IndicadorDemografico.anio_censo == anio,
        )
        pob_65 = base.filter(
            IndicadorDemografico.edad_quinquenal >= 65
        ).scalar() or 0
        pob_014 = base.filter(
            IndicadorDemografico.edad_quinquenal <= 10
        ).scalar() or 0

        indice = round((pob_65 / pob_014) * 100, 2) if pob_014 > 0 else None

        resultados.append(
            IndiceEnvejecimientoOut(
                codigo_comuna=comuna.codigo_comuna,
                nombre_comuna=comuna.nombre_comuna,
                anio_censo=anio,
                pob_65_mas=pob_65,
                pob_0_14=pob_014,
                indice_envejecimiento=indice,
            )
        )

    return resultados