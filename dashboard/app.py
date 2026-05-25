"""
dashboard/app.py
────────────────
Dashboard interactivo — Sistema de Monitoreo Demográfico Comunal de Aysén.
Semana 10: pirámide poblacional por sexo y grupo etario quinquenal.
"""

import os
import requests
import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go

# ── Configuración ─────────────────────────────────────────────────────────────
API_URL = os.getenv("API_URL", "http://localhost:8000")

app = dash.Dash(
    __name__,
    title="Monitoreo Demográfico Aysén",
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)

# ── Colores institucionales ───────────────────────────────────────────────────
C = {
    "primary":    "#00467F",
    "secondary":  "#1C5D91",
    "accent":     "#66844F",
    "orange":     "#D27D28",
    "background": "#F2F6FA",
    "card":       "#FFFFFF",
    "text":       "#505050",
    "text_light": "#888888",
    "border":     "#DDE4ED",
    "hombre":     "#1C5D91",
    "mujer":      "#D27D28",
}

GRUPOS_ETARIOS = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85]
LABELS_GRUPOS  = [f"{g}–{g+4}" if g < 85 else "85+" for g in GRUPOS_ETARIOS]


# ── Helpers de datos ──────────────────────────────────────────────────────────

def get_comunas() -> list[dict]:
    try:
        resp = requests.get(f"{API_URL}/comunas/", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def get_envejecimiento(codigo_comuna: int, anio: int) -> dict | None:
    try:
        resp = requests.get(
            f"{API_URL}/indicadores/envejecimiento/{codigo_comuna}",
            params={"anio": anio}, timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def get_sexo_edad(codigo_comuna: int, anio: int) -> dict | None:
    try:
        resp = requests.get(
            f"{API_URL}/indicadores/sexo-edad/{codigo_comuna}",
            params={"anio": anio}, timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


# ── Componentes reutilizables ─────────────────────────────────────────────────

def card(children, border_color: str = None, style_extra: dict = None) -> html.Div:
    base = {
        "backgroundColor": C["card"],
        "borderRadius": "8px",
        "padding": "1.5rem",
        "marginBottom": "1.2rem",
        "boxShadow": "0 1px 4px rgba(0,0,0,0.07)",
    }
    if border_color:
        base["borderLeft"] = f"4px solid {border_color}"
    if style_extra:
        base.update(style_extra)
    return html.Div(style=base, children=children)


def metrica(label: str, valor: str, color: str = None, tooltip: str = "") -> html.Div:
    return html.Div(
        title=tooltip,
        style={"minWidth": "140px"},
        children=[
            html.P(label, style={"margin": 0, "fontSize": "0.75rem",
                                  "color": C["text_light"], "textTransform": "uppercase",
                                  "letterSpacing": "0.04em"}),
            html.P(valor, style={"margin": "0.2rem 0 0 0", "fontSize": "1.5rem",
                                  "fontWeight": "bold", "color": color or C["primary"]}),
        ],
    )


def badge_ie(ie: float | None) -> html.Span:
    if ie is None:
        return html.Span("N/D", style={"color": C["text_light"]})
    color = C["accent"] if ie < 100 else C["orange"]
    label = "Población joven" if ie < 100 else "Población envejecida"
    return html.Span(label, style={
        "backgroundColor": color + "22",
        "color": color,
        "border": f"1px solid {color}55",
        "borderRadius": "4px",
        "padding": "0.15rem 0.6rem",
        "fontSize": "0.78rem",
        "fontWeight": "bold",
    })


def construir_piramide(data_sexo_edad: dict) -> go.Figure:
    """Construye el gráfico de pirámide poblacional."""
    distribucion = data_sexo_edad.get("distribucion", [])

    # Indexar por grupo etario y sexo
    hombres = {item["edad_quinquenal"]: item["cantidad"]
                for item in distribucion if item["sexo_label"] == "Hombre"}
    mujeres = {item["edad_quinquenal"]: item["cantidad"]
                for item in distribucion if item["sexo_label"] == "Mujer"}

    cant_hombres = [hombres.get(g, 0) for g in GRUPOS_ETARIOS]
    cant_mujeres = [mujeres.get(g, 0) for g in GRUPOS_ETARIOS]

    max_val = max(max(cant_hombres), max(cant_mujeres), 1)

    fig = go.Figure()

    # Barras de hombres (valores negativos para que vayan a la izquierda)
    fig.add_trace(go.Bar(
        y=LABELS_GRUPOS,
        x=[-v for v in cant_hombres],
        name="Hombre",
        orientation="h",
        marker_color=C["hombre"],
        hovertemplate="<b>Hombres</b><br>Grupo: %{y}<br>Cantidad: %{customdata:,}<extra></extra>",
        customdata=cant_hombres,
    ))

    # Barras de mujeres
    fig.add_trace(go.Bar(
        y=LABELS_GRUPOS,
        x=cant_mujeres,
        name="Mujer",
        orientation="h",
        marker_color=C["mujer"],
        hovertemplate="<b>Mujeres</b><br>Grupo: %{y}<br>Cantidad: %{customdata:,}<extra></extra>",
        customdata=cant_mujeres,
    ))

    fig.update_layout(
        barmode="overlay",
        bargap=0.1,
        xaxis=dict(
            tickvals=[-max_val, -max_val//2, 0, max_val//2, max_val],
            ticktext=[f"{max_val:,}", f"{max_val//2:,}", "0",
                      f"{max_val//2:,}", f"{max_val:,}"],
            title="Población",
            showgrid=True,
            gridcolor="#f0f0f0",
        ),
        yaxis=dict(title="Grupo etario", autorange=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="center", x=0.5),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=60, r=20, t=40, b=40),
        height=480,
        font=dict(family="Segoe UI, Arial", size=11, color=C["text"]),
    )

    # Línea central
    fig.add_vline(x=0, line_width=1, line_color=C["border"])

    return fig


# ── Layout ────────────────────────────────────────────────────────────────────

def build_layout() -> html.Div:
    comunas = get_comunas()
    opciones = [{"label": c["nombre_comuna"], "value": c["codigo_comuna"]}
                for c in comunas]

    return html.Div(
        style={"fontFamily": "'Segoe UI', Arial, sans-serif",
               "backgroundColor": C["background"], "minHeight": "100vh"},
        children=[

            # Header
            html.Div(
                style={"backgroundColor": C["primary"], "padding": "1rem 2rem",
                       "color": C["card"]},
                children=[
                    html.H1("Monitoreo Demográfico Comunal de Aysén",
                            style={"margin": 0, "fontSize": "1.2rem", "fontWeight": "bold"}),
                    html.P("CENSO INE 2017 y 2024 — Universidad de Aysén",
                           style={"margin": "0.2rem 0 0 0", "fontSize": "0.8rem", "opacity": 0.8}),
                ],
            ),

            # Filtros
            html.Div(
                style={"backgroundColor": C["card"], "padding": "1rem 2rem",
                       "borderBottom": f"1px solid {C['border']}",
                       "display": "flex", "gap": "1.5rem",
                       "alignItems": "flex-end", "flexWrap": "wrap"},
                children=[
                    html.Div([
                        html.Label("Comuna", style={"fontWeight": "600", "color": C["text"],
                                                     "display": "block", "marginBottom": "0.3rem",
                                                     "fontSize": "0.85rem"}),
                        dcc.Dropdown(id="selector-comuna", options=opciones,
                                     value=opciones[0]["value"] if opciones else None,
                                     clearable=False, style={"width": "200px"}),
                    ]),
                    html.Div([
                        html.Label("Año de censo", style={"fontWeight": "600", "color": C["text"],
                                                           "display": "block", "marginBottom": "0.3rem",
                                                           "fontSize": "0.85rem"}),
                        dcc.Dropdown(id="selector-anio",
                                     options=[{"label": "2024", "value": 2024},
                                              {"label": "2017", "value": 2017}],
                                     value=2024, clearable=False, style={"width": "110px"}),
                    ]),
                ],
            ),

            # Contenido
            html.Div(
                style={"padding": "1.5rem 2rem", "maxWidth": "1200px"},
                children=[

                    # Tarjeta resumen
                    html.Div(id="tarjeta-resumen"),

                    # Pirámide poblacional
                    card(
                        border_color=C["secondary"],
                        children=[
                            html.H3("Pirámide poblacional por sexo y grupo etario",
                                    style={"margin": "0 0 0.3rem 0",
                                           "color": C["primary"], "fontSize": "1rem"}),
                            html.P(
                                "Distribución de la población por grupos quinquenales de edad y sexo. "
                                "Los valores negativos corresponden a hombres (izquierda) y positivos a mujeres (derecha).",
                                style={"margin": "0 0 1rem 0", "fontSize": "0.78rem",
                                       "color": C["text_light"]},
                            ),
                            dcc.Graph(id="grafico-piramide", config={"displayModeBar": False}),
                        ],
                    ),

                    # Comparador — placeholder S12
                    card(
                        border_color=C["accent"],
                        children=[
                            html.H3("Comparador intercomunal",
                                    style={"margin": "0 0 0.5rem 0",
                                           "color": C["primary"], "fontSize": "1rem"}),
                            html.Div(
                                style={"height": "150px", "display": "flex",
                                       "alignItems": "center", "justifyContent": "center",
                                       "backgroundColor": C["background"], "borderRadius": "6px",
                                       "color": C["text_light"], "fontSize": "0.9rem"},
                                children="🗺️  Comparador intercomunal — disponible en Semana 12",
                            ),
                        ],
                    ),
                ],
            ),

            # Footer
            html.Div(
                style={"backgroundColor": C["primary"], "color": C["card"],
                       "textAlign": "center", "padding": "0.8rem",
                       "fontSize": "0.75rem", "opacity": 0.9, "marginTop": "2rem"},
                children="Universidad de Aysén — Ingeniería Civil Informática — TADS 2025",
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
    if not codigo_comuna or not anio:
        return html.P("Selecciona una comuna y un año.")

    data = get_envejecimiento(codigo_comuna, anio)
    if data is None:
        return html.P("Error al obtener datos.", style={"color": "red"})

    ie = data["indice_envejecimiento"]
    ie_texto = f"{ie:.2f}" if ie is not None else "N/D"
    ie_color  = C["accent"] if ie and ie < 100 else C["orange"]

    return card(
        border_color=C["primary"],
        children=[
            html.Div(
                style={"display": "flex", "justifyContent": "space-between",
                       "alignItems": "flex-start", "flexWrap": "wrap", "gap": "0.5rem"},
                children=[
                    html.H3(data["nombre_comuna"],
                            style={"margin": 0, "color": C["primary"], "fontSize": "1.2rem"}),
                    badge_ie(ie),
                ],
            ),
            html.Hr(style={"border": "none", "borderTop": f"1px solid {C['border']}",
                           "margin": "0.8rem 0"}),
            html.Div(
                style={"display": "flex", "gap": "2.5rem", "flexWrap": "wrap"},
                children=[
                    metrica("Año de censo",  str(anio)),
                    metrica("Población 0–14", f"{data['pob_0_14']:,}"),
                    metrica("Población 65+",  f"{data['pob_65_mas']:,}"),
                    metrica("Índice de envejecimiento", ie_texto, color=ie_color,
                            tooltip="(pob. 65+) / (pob. 0–14) × 100"),
                ],
            ),
        ],
    )


@callback(
    Output("grafico-piramide", "figure"),
    Input("selector-comuna", "value"),
    Input("selector-anio", "value"),
)
def actualizar_piramide(codigo_comuna: int, anio: int):
    if not codigo_comuna or not anio:
        return go.Figure()

    data = get_sexo_edad(codigo_comuna, anio)
    if data is None:
        fig = go.Figure()
        fig.add_annotation(text="Error al obtener datos", showarrow=False,
                           font=dict(size=14, color=C["text_light"]))
        return fig

    return construir_piramide(data)


# ── Punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=8050)
