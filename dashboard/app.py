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
    requests_pathname_prefix=os.getenv("DASH_PREFIX", "/"),
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

    grupos_activos = sorted(set(hombres.keys()) | set(mujeres.keys()))
    labels_activos = [f"{g}–{g+4}" if g < 85 else "85+" for g in grupos_activos]
    cant_hombres   = [hombres.get(g, 0) for g in grupos_activos]
    cant_mujeres   = [mujeres.get(g, 0) for g in grupos_activos]

    max_val = max(max(cant_hombres), max(cant_mujeres), 1)

    fig = go.Figure()

    # Barras de hombres (valores negativos para que vayan a la izquierda)
    fig.add_trace(go.Bar(
        y=labels_activos,
        x=[-v for v in cant_hombres],
        name="Hombre",
        orientation="h",
        marker_color=C["hombre"],
        hovertemplate="<b>Hombres</b><br>Grupo: %{y}<br>Cantidad: %{customdata:,}<extra></extra>",
        customdata=cant_hombres,
    ))

    # Barras de mujeres
    fig.add_trace(go.Bar(
        y=labels_activos,
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
                            html.Div(
                                style={"marginBottom": "1rem"},
                                children=[
                                    html.Label(
                                        "Filtrar por rango etario",
                                        style={"fontWeight": "600", "color": C["text"],
                                            "fontSize": "0.85rem", "display": "block",
                                            "marginBottom": "0.5rem"},
                                    ),
                                    dcc.RangeSlider(
                                        id="filtro-rango-etario",
                                        min=0,
                                        max=85,
                                        step=5,
                                        marks={i: f"{i}" if i % 20 == 0 or i == 85 else ""
                                            for i in range(0, 90, 5)},
                                        value=[0, 85],
                                        tooltip={"placement": "bottom", "always_visible": False},
                                    ),
                                ],
                            ),
                            dcc.Graph(id="grafico-piramide", config={"displayModeBar": False}),
                        ],
                    ),

                    # Comparador intercomunal
                    card(
                        border_color=C["accent"],
                        children=[
                            html.H3("Comparador intercomunal",
                                    style={"margin": "0 0 0.3rem 0",
                                        "color": C["primary"], "fontSize": "1rem"}),
                            html.P(
                                "Selecciona dos comunas para comparar sus indicadores demográficos.",
                                style={"margin": "0 0 1rem 0", "fontSize": "0.78rem",
                                    "color": C["text_light"]},
                            ),
                            # Selectores del comparador
                            html.Div(
                                style={"display": "flex", "gap": "1.5rem",
                                    "marginBottom": "1.2rem", "flexWrap": "wrap",
                                    "alignItems": "flex-end"},
                                children=[
                                    html.Div([
                                        html.Label("Comuna A", style={
                                            "fontWeight": "600", "color": C["primary"],
                                            "display": "block", "marginBottom": "0.3rem",
                                            "fontSize": "0.85rem",
                                        }),
                                        dcc.Dropdown(
                                            id="comparador-comuna-a",
                                            options=[],
                                            value=None,
                                            clearable=False,
                                            style={"width": "200px"},
                                        ),
                                    ]),
                                    html.Div([
                                        html.Label("Comuna B", style={
                                            "fontWeight": "600", "color": C["secondary"],
                                            "display": "block", "marginBottom": "0.3rem",
                                            "fontSize": "0.85rem",
                                        }),
                                        dcc.Dropdown(
                                            id="comparador-comuna-b",
                                            options=[],
                                            value=None,
                                            clearable=False,
                                            style={"width": "200px"},
                                        ),
                                    ]),
                                    html.Div([
                                        html.Label("Año de censo", style={
                                            "fontWeight": "600", "color": C["text"],
                                            "display": "block", "marginBottom": "0.3rem",
                                            "fontSize": "0.85rem",
                                        }),
                                        dcc.Dropdown(
                                            id="comparador-anio",
                                            options=[
                                                {"label": "2024", "value": 2024},
                                                {"label": "2017", "value": 2017},
                                            ],
                                            value=2024,
                                            clearable=False,
                                            style={"width": "110px"},
                                        ),
                                    ]),
                                ],
                            ),
                            # Resultado del comparador
                            html.Div(id="comparador-resultado"),
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
    Input("filtro-rango-etario", "value"),
)
def actualizar_piramide(codigo_comuna: int, anio: int, rango_etario: list):
    if not codigo_comuna or not anio:
        return go.Figure()

    data = get_sexo_edad(codigo_comuna, anio)
    if data is None:
        fig = go.Figure()
        fig.add_annotation(text="Error al obtener datos", showarrow=False,
                           font=dict(size=14, color=C["text_light"]))
        return fig

    # Filtrar distribución por rango etario seleccionado
    rango_min, rango_max = rango_etario
    data_filtrada = {
        **data,
        "distribucion": [
            item for item in data["distribucion"]
            if rango_min <= item["edad_quinquenal"] <= rango_max
        ]
    }

    return construir_piramide(data_filtrada)

@callback(
    Output("comparador-comuna-a", "options"),
    Output("comparador-comuna-a", "value"),
    Output("comparador-comuna-b", "options"),
    Output("comparador-comuna-b", "value"),
    Input("comparador-comuna-a", "id"),  # trigger único al cargar
)
def inicializar_comparador(_):
    """Carga las opciones de comunas en los selectores del comparador."""
    comunas = get_comunas()
    opciones = [{"label": c["nombre_comuna"], "value": c["codigo_comuna"]}
                for c in comunas]
    valor_a = opciones[0]["value"] if len(opciones) > 0 else None
    valor_b = opciones[1]["value"] if len(opciones) > 1 else None
    return opciones, valor_a, opciones, valor_b


@callback(
    Output("comparador-resultado", "children"),
    Input("comparador-comuna-a", "value"),
    Input("comparador-comuna-b", "value"),
    Input("comparador-anio", "value"),
)
def actualizar_comparador(comuna_a: int, comuna_b: int, anio: int):
    """Compara indicadores demográficos entre dos comunas."""
    if not comuna_a or not comuna_b or not anio:
        return html.P("Selecciona dos comunas para comparar.",
                      style={"color": C["text_light"]})

    data_a = get_envejecimiento(comuna_a, anio)
    data_b = get_envejecimiento(comuna_b, anio)

    if data_a is None or data_b is None:
        return html.P("Error al obtener datos.", style={"color": "red"})

    def fila_comparacion(label: str, val_a, val_b, tooltip: str = "") -> html.Tr:
        """Fila de la tabla con resaltado del valor mayor."""
        es_ie = "envejecimiento" in label.lower()
        # Para IE y pob_65+: mayor = más envejecida (naranja)
        # Para pob_0-14: mayor = más joven (verde)
        if isinstance(val_a, float) and isinstance(val_b, float):
            color_a = C["orange"] if (es_ie and val_a > val_b) else (
                C["accent"] if (not es_ie and val_a > val_b) else C["text"])
            color_b = C["orange"] if (es_ie and val_b > val_a) else (
                C["accent"] if (not es_ie and val_b > val_a) else C["text"])
            str_a = f"{val_a:.2f}"
            str_b = f"{val_b:.2f}"
        else:
            color_a = C["primary"] if val_a > val_b else C["text"]
            color_b = C["primary"] if val_b > val_a else C["text"]
            str_a = f"{val_a:,}"
            str_b = f"{val_b:,}"

        return html.Tr([
            html.Td(label, title=tooltip,
                    style={"padding": "0.6rem 1rem", "color": C["text_light"],
                           "fontSize": "0.82rem", "fontWeight": "600",
                           "textTransform": "uppercase", "letterSpacing": "0.03em"}),
            html.Td(str_a, style={"padding": "0.6rem 1rem", "textAlign": "center",
                                   "fontWeight": "bold", "fontSize": "1.1rem",
                                   "color": color_a}),
            html.Td(str_b, style={"padding": "0.6rem 1rem", "textAlign": "center",
                                   "fontWeight": "bold", "fontSize": "1.1rem",
                                   "color": color_b}),
        ])

    ie_a = data_a["indice_envejecimiento"] or 0.0
    ie_b = data_b["indice_envejecimiento"] or 0.0

    return html.Table(
        style={"width": "100%", "borderCollapse": "collapse"},
        children=[
            # Encabezado
            html.Thead(html.Tr([
                html.Th("Indicador", style={"padding": "0.6rem 1rem",
                                             "borderBottom": f"2px solid {C['border']}",
                                             "textAlign": "left", "color": C["text_light"],
                                             "fontSize": "0.78rem"}),
                html.Th(
                    html.Div([
                        html.Span(data_a["nombre_comuna"],
                                  style={"fontWeight": "bold", "color": C["primary"],
                                         "fontSize": "1rem"}),
                        html.Br(),
                        badge_ie(ie_a),
                    ]),
                    style={"padding": "0.6rem 1rem", "textAlign": "center",
                           "borderBottom": f"2px solid {C['primary']}"}
                ),
                html.Th(
                    html.Div([
                        html.Span(data_b["nombre_comuna"],
                                  style={"fontWeight": "bold", "color": C["secondary"],
                                         "fontSize": "1rem"}),
                        html.Br(),
                        badge_ie(ie_b),
                    ]),
                    style={"padding": "0.6rem 1rem", "textAlign": "center",
                           "borderBottom": f"2px solid {C['secondary']}"}
                ),
            ])),
            # Filas
            html.Tbody([
                fila_comparacion("Año de censo", anio, anio),
                fila_comparacion("Población 0–14", data_a["pob_0_14"], data_b["pob_0_14"]),
                fila_comparacion("Población 65+", data_a["pob_65_mas"], data_b["pob_65_mas"]),
                fila_comparacion(
                    "Índice de envejecimiento",
                    ie_a, ie_b,
                    tooltip="(pob. 65+) / (pob. 0–14) × 100"
                ),
            ]),
        ],
    )

# ── Punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=8050)
