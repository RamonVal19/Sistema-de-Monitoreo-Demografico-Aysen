"""
Tests — Sprint 7 / RF1.

Cobertura:
  - Pipeline ETL: extracción, transformación, comportamiento de edad reservada
  - API endpoints: /comunas, /indicadores/sexo-edad, /indicadores/envejecimiento

Estrategia de BD: SQLite en memoria (autónoma, sin PostgreSQL).
El override de `get_db` sustituye la sesión de producción en cada test.

Ejecutar:
    pytest tests/test_api.py -v
"""

import pytest
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from api.database import Base, get_db
from etl.pipeline import transformar, EDAD_RESERVADA, COMUNAS_AYSEN
from api.models import Comuna, IndicadorDemografico, Usuario
from api.auth import hash_password
# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES COMPARTIDOS
# ═════════════════════════════════════════════════════════════════════════════

TEST_DB_URL = "sqlite://"

engine_test = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine_test
)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine_test)
    db = TestingSessionLocal()

    comunas_seed = [
        Comuna(codigo_comuna=11201, nombre_comuna="Aysén",     codigo_region=11),
        Comuna(codigo_comuna=11202, nombre_comuna="Cisnes",    codigo_region=11),
        Comuna(codigo_comuna=11101, nombre_comuna="Coyhaique", codigo_region=11),
    ]
    db.add_all(comunas_seed)
    db.commit()

    # Usuario admin de prueba
    usuario_seed = Usuario(
        username="admin_test",
        email="admin@test.com",
        hashed_password=hash_password("test1234"),
        is_active=True,
    )
    db.add(usuario_seed)
    db.commit()

    indicadores_seed = [
        # Aysén 2024 — grupo joven 0–14 (2 personas)
        IndicadorDemografico(
            codigo_comuna=11201, anio_censo=2024,
            sexo=1, sexo_label="Hombre", edad=10, edad_quinquenal=10,
        ),
        IndicadorDemografico(
            codigo_comuna=11201, anio_censo=2024,
            sexo=2, sexo_label="Mujer", edad=8, edad_quinquenal=5,
        ),
        # Aysén 2024 — adultos mayores 65+ (2 personas)
        IndicadorDemografico(
            codigo_comuna=11201, anio_censo=2024,
            sexo=1, sexo_label="Hombre", edad=70, edad_quinquenal=70,
        ),
        IndicadorDemografico(
            codigo_comuna=11201, anio_censo=2024,
            sexo=2, sexo_label="Mujer", edad=68, edad_quinquenal=65,
        ),
        # Aysén 2024 — edad reservada (NULL en BD)
        IndicadorDemografico(
            codigo_comuna=11201, anio_censo=2024,
            sexo=1, sexo_label="Hombre", edad=None, edad_quinquenal=30,
        ),
        # Cisnes 2024
        IndicadorDemografico(
            codigo_comuna=11202, anio_censo=2024,
            sexo=2, sexo_label="Mujer", edad=45, edad_quinquenal=45,
        ),
        # Aysén 2017
        IndicadorDemografico(
            codigo_comuna=11201, anio_censo=2017,
            sexo=1, sexo_label="Hombre", edad=5, edad_quinquenal=5,
        ),
    ]
    db.add_all(indicadores_seed)
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine_test)


@pytest.fixture(autouse=True)
def override_get_db():
    def _get_test_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _df(filas: list[dict]) -> pd.DataFrame:
    """Construye un DataFrame mínimo con las columnas INE requeridas."""
    return pd.DataFrame(filas)


BASE_FILA = dict(region=11, comuna=11201, sexo=1, edad=30, edad_quinquenal=30)


# ═════════════════════════════════════════════════════════════════════════════
# TESTS DEL PIPELINE ETL
# ═════════════════════════════════════════════════════════════════════════════

class TestETLTransformacion:
    """Prueba la función `transformar` de etl/pipeline.py de forma aislada."""

    def test_filtra_otras_regiones(self):
        df = _df([BASE_FILA, {**BASE_FILA, "region": 13, "comuna": 13101}])
        resultado = transformar(df, 2024)
        assert len(resultado) == 1
        assert (resultado["region"] == 11).all()

    def test_edad_reservada_se_convierte_a_null(self):
        df = _df([
            {**BASE_FILA, "edad": EDAD_RESERVADA},
            {**BASE_FILA, "edad": 25, "sexo": 2},
        ])
        resultado = transformar(df, 2024)
        edades = resultado["edad"].tolist()
        assert pd.isna(edades[0])
        assert edades[1] == 25

    def test_solo_edad_reservada_es_null(self):
        """Verifica que únicamente -66 → NULL, no cualquier valor negativo."""
        df = _df([
            {**BASE_FILA, "edad": EDAD_RESERVADA},
            {**BASE_FILA, "edad": 40, "sexo": 2},
        ])
        resultado = transformar(df, 2024)
        assert resultado["edad"].isna().sum() == 1
        assert resultado["edad"].notna().sum() == 1

    def test_agrega_nombre_comuna(self):
        df = _df([BASE_FILA])
        resultado = transformar(df, 2024)
        assert "nombre_comuna" in resultado.columns
        assert resultado.iloc[0]["nombre_comuna"] == "Aysén"

    def test_agrega_sexo_label(self):
        df = _df([BASE_FILA, {**BASE_FILA, "sexo": 2, "edad": 31}])
        resultado = transformar(df, 2024)
        assert set(resultado["sexo_label"].tolist()) == {"Hombre", "Mujer"}

    def test_descarta_comunas_fuera_de_aysen(self):
        df = _df([BASE_FILA, {**BASE_FILA, "comuna": 99999}])
        resultado = transformar(df, 2024)
        assert len(resultado) == 1

    def test_descarta_sexo_invalido(self):
        df = _df([BASE_FILA, {**BASE_FILA, "sexo": 9, "edad": 31}])
        resultado = transformar(df, 2024)
        assert len(resultado) == 1

    def test_catalogo_tiene_exactamente_10_comunas(self):
        assert len(COMUNAS_AYSEN) == 10

    def test_todos_los_codigos_son_de_region_11(self):
        assert all(str(c).startswith("11") for c in COMUNAS_AYSEN)


# ═════════════════════════════════════════════════════════════════════════════
# TESTS DE ESTADO
# ═════════════════════════════════════════════════════════════════════════════

class TestEstado:
    def test_root_retorna_200(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["estado"] == "activo"

    def test_health_retorna_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ═════════════════════════════════════════════════════════════════════════════
# TESTS DE /comunas
# ═════════════════════════════════════════════════════════════════════════════

class TestComunas:
    def test_listar_retorna_lista(self):
        resp = client.get("/comunas/")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_listar_ordenadas_por_codigo(self):
        codigos = [c["codigo_comuna"] for c in client.get("/comunas/").json()]
        assert codigos == sorted(codigos)

    def test_obtener_existente(self):
        resp = client.get("/comunas/11201")
        assert resp.status_code == 200
        assert resp.json()["nombre_comuna"] == "Aysén"

    def test_obtener_inexistente_retorna_404(self):
        assert client.get("/comunas/99999").status_code == 404

    def test_schema_tiene_campos_esperados(self):
        data = client.get("/comunas/11201").json()
        for campo in ["codigo_comuna", "nombre_comuna", "codigo_region"]:
            assert campo in data
        assert data["codigo_region"] == 11


# ═════════════════════════════════════════════════════════════════════════════
# TESTS DE /indicadores/sexo-edad
# ═════════════════════════════════════════════════════════════════════════════

class TestDistribucionSexoEdad:
    def test_retorna_distribucion_valida(self):
        resp = client.get("/indicadores/sexo-edad/11201?anio=2024")
        assert resp.status_code == 200
        data = resp.json()
        assert data["codigo_comuna"] == 11201
        assert data["anio_censo"] == 2024
        assert len(data["distribucion"]) > 0

    def test_items_tienen_campos_correctos(self):
        item = client.get("/indicadores/sexo-edad/11201?anio=2024").json()["distribucion"][0]
        for campo in ["edad_quinquenal", "sexo_label", "cantidad"]:
            assert campo in item

    def test_anio_por_defecto_es_2024(self):
        assert client.get("/indicadores/sexo-edad/11201").json()["anio_censo"] == 2024

    def test_anio_invalido_retorna_422(self):
        assert client.get("/indicadores/sexo-edad/11201?anio=2000").status_code == 422

    def test_comuna_inexistente_retorna_404(self):
        assert client.get("/indicadores/sexo-edad/99999?anio=2024").status_code == 404

    def test_diferencia_datos_entre_anios(self):
        total = lambda anio: sum(
            i["cantidad"]
            for i in client.get(f"/indicadores/sexo-edad/11201?anio={anio}").json()["distribucion"]
        )
        assert total(2024) > total(2017)


# ═════════════════════════════════════════════════════════════════════════════
# TESTS DE /indicadores/envejecimiento
# ═════════════════════════════════════════════════════════════════════════════

class TestIndiceEnvejecimiento:
    def test_calculo_correcto(self):
        data = client.get("/indicadores/envejecimiento/11201?anio=2024").json()
        # seed: 2 en 65+ y 2 en 0–14 → IE = 100.0
        assert data["pob_65_mas"] == 2
        assert data["pob_0_14"] == 2
        assert data["indice_envejecimiento"] == 100.0

    def test_excluye_edades_null_del_calculo(self):
        # La persona con edad=NULL no debe modificar el índice
        data = client.get("/indicadores/envejecimiento/11201?anio=2024").json()
        assert data["indice_envejecimiento"] == 100.0

    def test_anio_invalido_retorna_422(self):
        assert client.get("/indicadores/envejecimiento/11201?anio=1990").status_code == 422

    def test_comuna_inexistente_retorna_404(self):
        assert client.get("/indicadores/envejecimiento/99999").status_code == 404

    def test_listado_regional_retorna_todas_las_comunas(self):
        data = client.get("/indicadores/envejecimiento?anio=2024").json()
        assert len(data) == 3
        codigos = {c["codigo_comuna"] for c in data}
        assert {11201, 11202, 11101}.issubset(codigos)

    def test_schema_tiene_campos_esperados(self):
        data = client.get("/indicadores/envejecimiento/11201").json()
        for campo in ["codigo_comuna", "nombre_comuna", "anio_censo",
                      "pob_65_mas", "pob_0_14", "indice_envejecimiento"]:
            assert campo in data


# ═════════════════════════════════════════════════════════════════════════════
# TESTS DE /admin
# ═════════════════════════════════════════════════════════════════════════════

class TestAdmin:
    def test_login_exitoso(self):
        resp = client.post(
            "/admin/login",
            data={"username": "admin_test", "password": "test1234"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["username"] == "admin_test"

    def test_login_credenciales_incorrectas(self):
        resp = client.post(
            "/admin/login",
            data={"username": "admin_test", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    def test_login_usuario_inexistente(self):
        resp = client.post(
            "/admin/login",
            data={"username": "noexiste", "password": "test1234"},
        )
        assert resp.status_code == 401

    def test_estado_bd_sin_token_retorna_401(self):
        resp = client.get("/admin/estado-bd")
        assert resp.status_code == 401

    def test_estado_bd_con_token_valido(self):
        # Obtener token
        token = client.post(
            "/admin/login",
            data={"username": "admin_test", "password": "test1234"},
        ).json()["access_token"]

        resp = client.get(
            "/admin/estado-bd",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_registros" in data
        assert "por_anio" in data
        assert "por_comuna" in data

    def test_estado_bd_token_invalido_retorna_401(self):
        resp = client.get(
            "/admin/estado-bd",
            headers={"Authorization": "Bearer token_invalido"},
        )
        assert resp.status_code == 401

    def test_etl_status_sin_token_retorna_401(self):
        resp = client.get("/admin/etl-status")
        assert resp.status_code == 401

    def test_etl_status_con_token_valido(self):
        token = client.post(
            "/admin/login",
            data={"username": "admin_test", "password": "test1234"},
        ).json()["access_token"]

        resp = client.get(
            "/admin/etl-status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "en_curso" in data
        assert "ultimo_resultado" in data