"""
Modelos ORM — tablas del sistema de monitoreo demográfico.

Tablas:
  - comunas                  : catálogo de las 10 comunas de Aysén.
  - indicadores_demograficos : una fila por persona del CENSO INE
                               (2017 y/o 2024), post-ETL.
"""

from sqlalchemy import (
    Column, Integer, String, SmallInteger,
    ForeignKey, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from api.database import Base


class Comuna(Base):
    __tablename__ = "comunas"

    # Código comunal INE como PK natural (ej. 11201 → Aysén)
    codigo_comuna = Column(Integer, primary_key=True, index=True)
    nombre_comuna = Column(String(100), nullable=False, unique=True)
    codigo_region = Column(SmallInteger, nullable=False, default=11)

    indicadores = relationship(
        "IndicadorDemografico",
        back_populates="comuna",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Comuna {self.codigo_comuna} – {self.nombre_comuna}>"


class IndicadorDemografico(Base):
    """
    Una fila por persona registrada en el CSV del INE post-ETL.

    Columnas de origen (CSV):
        region, comuna, sexo, edad, edad_quinquenal, nombre_comuna, sexo_label

    Decisiones de limpieza:
        - edad: el INE codifica "prefiero no responder" como -66.
          El pipeline ETL convierte ese valor a NULL (edad reservada).
          Los cálculos de indicadores filtran WHERE edad IS NOT NULL.
        - comunas y sexos fuera del dominio se descartan en el ETL.
    """
    __tablename__ = "indicadores_demograficos"

    id = Column(Integer, primary_key=True, autoincrement=True)

    codigo_comuna = Column(
        Integer,
        ForeignKey("comunas.codigo_comuna", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    anio_censo = Column(SmallInteger, nullable=False, index=True)

    sexo       = Column(SmallInteger, nullable=False)   # 1 = Hombre, 2 = Mujer
    sexo_label = Column(String(10),   nullable=False)   # 'Hombre' | 'Mujer'

    # NULL = persona que reservó su edad (INE código -66)
    edad            = Column(Integer,   nullable=True)
    edad_quinquenal = Column(SmallInteger, nullable=False)

    __table_args__ = (
    CheckConstraint("sexo IN (1, 2)",            name="ck_sexo_valido"),
    CheckConstraint("anio_censo IN (2017, 2024)", name="ck_anio_valido"),
)

    comuna = relationship("Comuna", back_populates="indicadores")

    def __repr__(self) -> str:
        return (
            f"<IndicadorDemografico "
            f"comuna={self.codigo_comuna} censo={self.anio_censo} "
            f"sexo={self.sexo_label} edad={self.edad}>"
        )