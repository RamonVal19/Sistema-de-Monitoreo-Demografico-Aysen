"""
Schemas Pydantic — contratos de entrada/salida de la API.

Separa la capa de serialización de los modelos ORM (buena práctica FastAPI).
"""

from pydantic import BaseModel, Field, ConfigDict


# ── Comunas ───────────────────────────────────────────────────────────────────

class ComunaBase(BaseModel):
    codigo_comuna: int
    nombre_comuna: str
    codigo_region: int


class ComunaOut(ComunaBase):
    model_config = ConfigDict(from_attributes=True)


# ── Indicadores demográficos (raw) ────────────────────────────────────────────

class IndicadorOut(BaseModel):
    id: int
    codigo_comuna: int
    anio_censo: int
    sexo: int
    sexo_label: str
    edad: int
    edad_quinquenal: int

    model_config = ConfigDict(from_attributes=True)


# ── Distribución por sexo y grupo etario (agregado) ──────────────────────────

class GrupoEtarioItem(BaseModel):
    edad_quinquenal: int = Field(description="Inicio del grupo quinquenal (0, 5, 10, …)")
    sexo_label: str = Field(description="'Hombre' o 'Mujer'")
    cantidad: int = Field(description="Número de personas en este grupo")


class DistribucionSexoEdadOut(BaseModel):
    codigo_comuna: int
    nombre_comuna: str
    anio_censo: int
    distribucion: list[GrupoEtarioItem]


# ── Índice de envejecimiento ──────────────────────────────────────────────────

class IndiceEnvejecimientoOut(BaseModel):
    codigo_comuna: int
    nombre_comuna: str
    anio_censo: int
    pob_65_mas: int = Field(description="Población de 65 años o más")
    pob_0_14: int = Field(description="Población de 0 a 14 años")
    indice_envejecimiento: float | None = Field(
        description="(pob. 65+) / (pob. 0–14) × 100. "
                    "None si pob_0_14 = 0."
    )