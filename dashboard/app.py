"""
dashboard/app.py
────────────────
Dashboard interactivo — Sistema de Monitoreo Demográfico Comunal de Aysén.
Consume la API REST para obtener datos demográficos.

Semana 9: estructura base, layout, selectores y conexión a la API.
"""

import requests  # Para consumir endpoints HTTP de la API REST
import dash
from dash import dcc, html, Input, Output, callback

# ── Configuración ─────────────────────────────────────────────────────────────
API_URL = "http://localhost:8000"  # local; en producción usar variable de entorno

# ── Inicialización ────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    title="Monitoreo Demográfico Aysén",
    suppress_callback_exceptions=True,  # Permite callbacks que referencia IDs que no existen en el layout inicial
)

# ── Colores institucionales ───────────────────────────────────────────────────
COLORS = {
    "primary":    "#00467F",   # uaysenblue
    "secondary":  "#1C5D91",   # uaysenblue2
    "accent":     "#66844F",   # softgreen
    "background": "#F2F6FA",   # uaysenlight
    "text":       "#505050",   # uaysengray
    "white":      "#FFFFFF",
}


def get_comunas() -> list[dict]:
    """
    Obtiene el catálogo de comunas desde GET /comunas/.
    
    Retorna lista de dicts: [{"codigo_comuna": 11201, "nombre_comuna": "Aysén"}, ...]
    Si hay error (API caída, timeout), retorna lista vacía.
    """
    try:
        resp = requests.get(f"{API_URL}/comunas/", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


# ── Layout ────────────────────────────────────────────────────────────────────
def build_layout() -> html.Div:
    """
    Construye el layout inicial del dashboard.
    
    Se llama como función (no como atributo) para que get_comunas()
    se ejecute al iniciar, permitiendo que los dropdowns se llenen dinámicamente.
    """
    comunas = get_comunas()
    opciones_comunas = [
        {"label": c["nombre_comuna"], "value": c["codigo_comuna"]}
        for c in comunas
    ]

    return html.Div(
        style={"fontFamily": "Arial, sans-serif", "backgroundColor": COLORS["background"], "minHeight": "100vh"},
        children=[

            # ── Header ───────────────────────────────────────────────────────
            html.Div(
                style={
                    "backgroundColor": COLORS["primary"],
                    "padding": "1.2rem 2rem",
                    "color": COLORS["white"],
                },
                children=[
                    html.H1(
                        "Sistema de Monitoreo Demográfico Comunal de Aysén",
                        style={"margin": 0, "fontSize": "1.4rem", "fontWeight": "bold"},
                    ),
                    html.P(
                        "CENSO INE 2017 y 2024 — Universidad de Aysén",
                        style={"margin": "0.3rem 0 0 0", "fontSize": "0.85rem", "opacity": 0.85},
                    ),
                ],
            ),

            # ── Panel de filtros ─────────────────────────────────────────────
            html.Div(
                style={
                    "backgroundColor": COLORS["white"],
                    "padding": "1.2rem 2rem",
                    "borderBottom": f"2px solid {COLORS['background']}",
                    "display": "flex",
                    "gap": "2rem",
                    "alignItems": "flex-end",
                    "flexWrap": "wrap",
                },
                children=[
                    html.Div([
                        html.Label(
                            "Comuna",
                            style={"fontWeight": "bold", "color": COLORS["text"],
                                   "display": "block", "marginBottom": "0.4rem"},
                        ),
                        dcc.Dropdown(
                            id="selector-comuna",
                            options=opciones_comunas,
                            value=opciones_comunas[0]["value"] if opciones_comunas else None,
                            clearable=False,
                            style={"width": "220px"},
                        ),
                    ]),
                    html.Div([
                        html.Label(
                            "Año de censo",
                            style={"fontWeight": "bold", "color": COLORS["text"],
                                   "display": "block", "marginBottom": "0.4rem"},
                        ),
                        dcc.Dropdown(
                            id="selector-anio",
                            options=[
                                {"label": "2024", "value": 2024},
                                {"label": "2017", "value": 2017},
                            ],
                            value=2024,
                            clearable=False,
                            style={"width": "120px"},
                        ),
                    ]),
                ],
            ),

            # ── Área de contenido ─────────────────────────────────────────────
            html.Div(
                style={"padding": "2rem"},
                children=[

                    # Tarjeta de resumen
                    html.Div(
                        id="tarjeta-resumen",
                        style={
                            "backgroundColor": COLORS["white"],
                            "borderRadius": "8px",
                            "padding": "1.5rem",
                            "marginBottom": "1.5rem",
                            "boxShadow": "0 1px 4px rgba(0,0,0,0.08)",
                            "borderLeft": f"4px solid {COLORS['primary']}",
                        },
                    ),

                    # Placeholder pirámide (S11)
                    html.Div(
                        style={
                            "backgroundColor": COLORS["white"],
                            "borderRadius": "8px",
                            "padding": "3rem",
                            "textAlign": "center",
                            "color": COLORS["text"],
                            "boxShadow": "0 1px 4px rgba(0,0,0,0.08)",
                        },
                        children=[
                            html.P("📊", style={"fontSize": "3rem", "margin": 0}),
                            html.P(
                                "Pirámide poblacional — disponible en Semana 11",
                                style={"fontSize": "1rem", "marginTop": "0.5rem"},
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


app.layout = build_layout


# ── Callbacks ─────────────────────────────────────────────────────────────────

@callback(
    Output("tarjeta-resumen", "children"),
    Input("selector-comuna", "value"),
    Input("selector-anio", "value"),
)
def actualizar_resumen(codigo_comuna: int, anio: int):
    """
    Se dispara cuando cambia la comuna o el año en los dropdowns.
    
    Consume GET /indicadores/envejecimiento/{codigo_comuna}?anio=XXXX
    y renderiza una tarjeta con métricas clave: población 0-14, 65+, índice envejecimiento.
    """
    if not codigo_comuna or not anio:
        return html.P("Selecciona una comuna y un año.")

    try:
        resp = requests.get(
            f"{API_URL}/indicadores/envejecimiento/{codigo_comuna}",
            params={"anio": anio},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return html.P(f"Error al obtener datos: {exc}", style={"color": "red"})

    ie = data["indice_envejecimiento"]
    ie_texto = f"{ie:.2f}" if ie is not None else "N/D"
    # Cambia color según valor: verde si < 100 (población joven), rojo si >= 100 (envejecida)
    ie_color  = COLORS["accent"] if ie and ie < 100 else "#C0392B"

    return [
        html.H3(
            data["nombre_comuna"],
            style={"margin": "0 0 0.8rem 0", "color": COLORS["primary"]},
        ),
        html.Div(
            style={"display": "flex", "gap": "3rem", "flexWrap": "wrap"},
            children=[
                _metrica("Año de censo",     str(anio)),
                _metrica("Población 0–14",   f"{data['pob_0_14']:,}"),
                _metrica("Población 65+",    f"{data['pob_65_mas']:,}"),
                _metrica(
                    "Índice de envejecimiento",
                    ie_texto,
                    color=ie_color,
                    tooltip="(pob. 65+) / (pob. 0–14) × 100",
                ),
            ],
        ),
    ]


def _metrica(label: str, valor: str, color: str = None, tooltip: str = None) -> html.Div:
    """
    Componente reutilizable que renderiza una métrica.
    
    Estructura:
      label (gris pequeño)
      valor (grande y negrita, color customizable)
    
    Useful en tarjetas de resumen y dashboards numéricos.
    """
    return html.Div(
        title=tooltip or "",
        children=[
            html.P(label, style={"margin": 0, "fontSize": "0.78rem", "color": COLORS["text"]}),
            html.P(valor, style={
                "margin": "0.2rem 0 0 0",
                "fontSize": "1.4rem",
                "fontWeight": "bold",
                "color": color or COLORS["primary"],
            }),
        ],
    )


# ── Punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=8050)