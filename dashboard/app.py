"""
dashboard/app.py
────────────────
Dashboard interactivo — Sistema de Monitoreo Demográfico Comunal de Aysén.
Consume la API REST para obtener datos demográficos.

Semana 9: estructura base, layout, selectores, tarjeta resumen y
          estructura preparada para pirámide poblacional (S11).
"""

import os  # Para leer variables de entorno (API_URL en producción)
import requests  # Para consumir endpoints HTTP de la API REST
import dash
from dash import dcc, html, Input, Output, callback

# ── Configuración ─────────────────────────────────────────────────────────────
API_URL = os.getenv("API_URL", "http://localhost:8000")

# ── Inicialización ────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    title="Monitoreo Demográfico Aysén",
    suppress_callback_exceptions=True,  # Permite callbacks que referencian IDs no presentes en el layout inicial
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
}


# ── Helpers de datos ──────────────────────────────────────────────────────────

def get_comunas() -> list[dict]:
    """Obtiene el catálogo de comunas desde GET /comunas/, retorna lista vacía si falla."""
    try:
        resp = requests.get(f"{API_URL}/comunas/", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def get_envejecimiento(codigo_comuna: int, anio: int) -> dict | None:
    """
    Obtiene indicador de envejecimiento desde GET /indicadores/envejecimiento/{id}?anio=X
    
    Retorna dict con keys: nombre_comuna, pob_0_14, pob_65_mas, indice_envejecimiento
    Si hay error (API caída, timeout, 404), retorna None.
    """
    try:
        resp = requests.get(
            f"{API_URL}/indicadores/envejecimiento/{codigo_comuna}",
            params={"anio": anio},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


# ── Componentes reutilizables ─────────────────────────────────────────────────

def card(children, border_color: str = None, style_extra: dict = None) -> html.Div:
    """
    Componente contenedor con estilos consistentes (fondo blanco, sombra, esquinas redondeadas).
    
    Params:
        children: contenido dentro de la tarjeta (html elements)
        border_color: color de borde izquierdo (ej: C["primary"], opcional)
        style_extra: dict de estilos adicionales para personalizar (opcional)
    """
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
    """
    Componente para mostrar una métrica (ej: Población 0–14 = 1,230).
    
    Estructura visual: label (pequeño, gris) encima de valor (grande, negrita, color customizable).
    El tooltip aparece al pasar el mouse sobre el número.
    """
    return html.Div(
        title=tooltip,
        style={"minWidth": "140px"},
        children=[
            html.P(
                label,
                style={"margin": 0, "fontSize": "0.75rem",
                       "color": C["text_light"], "textTransform": "uppercase",
                       "letterSpacing": "0.04em"},
            ),
            html.P(
                valor,
                style={"margin": "0.2rem 0 0 0", "fontSize": "1.5rem",
                       "fontWeight": "bold", "color": color or C["primary"]},
            ),
        ],
    )


def badge_ie(ie: float | None) -> html.Span:
    """
    Badge (etiqueta de color) que clasifica la población según índice de envejecimiento.
    
    Lógica: IE < 100 → "Población joven" (verde), IE >= 100 → "Población envejecida" (naranja).
    Si IE es None, retorna "N/D" en gris.
    """
    if ie is None:
        return html.Span("N/D", style={"color": C["text_light"]})
    color = C["accent"] if ie < 100 else C["orange"]
    label = "Población joven" if ie < 100 else "Población envejecida"
    return html.Span(
        label,
        style={
            "backgroundColor": color + "22",  # Fondo semiclaro (opacidad 22 en hex)
            "color": color,
            "border": f"1px solid {color}55",
            "borderRadius": "4px",
            "padding": "0.15rem 0.6rem",
            "fontSize": "0.78rem",
            "fontWeight": "bold",
        },
    )


# ── Layout ────────────────────────────────────────────────────────────────────

def build_layout() -> html.Div:
    """
    Construye el layout inicial del dashboard.
    
    Se llama como función (no como atributo directo) para que get_comunas() se ejecute
    al iniciar, permitiendo que los dropdowns se llenen dinámicamente desde la API.
    """
    comunas = get_comunas()
    opciones = [
        {"label": c["nombre_comuna"], "value": c["codigo_comuna"]}
        for c in comunas
    ]

    return html.Div(
        style={"fontFamily": "'Segoe UI', Arial, sans-serif",
               "backgroundColor": C["background"], "minHeight": "100vh"},
        children=[

            # ── Header ───────────────────────────────────────────────────────
            html.Div(
                style={
                    "backgroundColor": C["primary"],
                    "padding": "1rem 2rem",
                    "color": C["card"],
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "1rem",
                },
                children=[
                    html.Div([
                        html.H1(
                            "Monitoreo Demográfico Comunal de Aysén",
                            style={"margin": 0, "fontSize": "1.2rem", "fontWeight": "bold"},
                        ),
                        html.P(
                            "CENSO INE 2017 y 2024 — Universidad de Aysén",
                            style={"margin": "0.2rem 0 0 0", "fontSize": "0.8rem", "opacity": 0.8},
                        ),
                    ]),
                ],
            ),

            # ── Panel de filtros ─────────────────────────────────────────────
            html.Div(
                style={
                    "backgroundColor": C["card"],
                    "padding": "1rem 2rem",
                    "borderBottom": f"1px solid {C['border']}",
                    "display": "flex",
                    "gap": "1.5rem",
                    "alignItems": "flex-end",
                    "flexWrap": "wrap",
                },
                children=[
                    html.Div([
                        html.Label("Comuna", style={
                            "fontWeight": "600", "color": C["text"],
                            "display": "block", "marginBottom": "0.3rem",
                            "fontSize": "0.85rem",
                        }),
                        dcc.Dropdown(
                            id="selector-comuna",
                            options=opciones,
                            value=opciones[0]["value"] if opciones else None,
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
                            id="selector-anio",
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

            # ── Contenido principal ───────────────────────────────────────────
            html.Div(
                style={"padding": "1.5rem 2rem", "maxWidth": "1200px"},
                children=[

                    # Tarjeta de resumen se actualiza con el callback
                    html.Div(id="tarjeta-resumen"),

                    # Sección pirámide placeholder hasta S11
                    card(
                        border_color=C["secondary"],
                        children=[
                            html.H3(
                                "Pirámide poblacional por sexo y grupo etario",
                                style={"margin": "0 0 0.5rem 0",
                                       "color": C["primary"], "fontSize": "1rem"},
                            ),
                            html.Div(
                                id="grafico-piramide",
                                style={
                                    "height": "320px",
                                    "display": "flex",
                                    "alignItems": "center",
                                    "justifyContent": "center",
                                    "backgroundColor": C["background"],
                                    "borderRadius": "6px",
                                    "color": C["text_light"],
                                    "fontSize": "0.9rem",
                                },
                                children="📊  Pirámide poblacional — disponible en Semana 11",
                            ),
                        ],
                    ),

                    # Sección comparador placeholder hasta S12
                    card(
                        border_color=C["accent"],
                        children=[
                            html.H3(
                                "Comparador intercomunal",
                                style={"margin": "0 0 0.5rem 0",
                                       "color": C["primary"], "fontSize": "1rem"},
                            ),
                            html.Div(
                                style={
                                    "height": "200px",
                                    "display": "flex",
                                    "alignItems": "center",
                                    "justifyContent": "center",
                                    "backgroundColor": C["background"],
                                    "borderRadius": "6px",
                                    "color": C["text_light"],
                                    "fontSize": "0.9rem",
                                },
                                children="🗺️  Comparador intercomunal — disponible en Semana 12",
                            ),
                        ],
                    ),

                ],
            ),

            # ── Footer ────────────────────────────────────────────────────────
            html.Div(
                style={
                    "backgroundColor": C["primary"],
                    "color": C["card"],
                    "textAlign": "center",
                    "padding": "0.8rem",
                    "fontSize": "0.75rem",
                    "opacity": 0.9,
                    "marginTop": "2rem",
                },
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
    """
    Se dispara automáticamente cuando cambia la comuna o el año en los dropdowns.
    
    Consume GET /indicadores/envejecimiento/{codigo_comuna}?anio=XXXX
    y renderiza tarjeta con métricas clave: población 0-14, 65+, índice envejecimiento
    además de un badge visual que clasifica la población.
    """
    if not codigo_comuna or not anio:
        return html.P("Selecciona una comuna y un año.")

    data = get_envejecimiento(codigo_comuna, anio)
    if data is None:
        return html.P("Error al obtener datos de la API.", style={"color": "red"})

    ie = data["indice_envejecimiento"]
    ie_texto = f"{ie:.2f}" if ie is not None else "N/D"
    ie_color = C["accent"] if ie and ie < 100 else C["orange"]

    return card(
        border_color=C["primary"],
        children=[
            html.Div(
                style={"display": "flex", "justifyContent": "space-between",
                       "alignItems": "flex-start", "flexWrap": "wrap", "gap": "0.5rem"},
                children=[
                    html.H3(
                        data["nombre_comuna"],
                        style={"margin": 0, "color": C["primary"], "fontSize": "1.2rem"},
                    ),
                    badge_ie(ie),
                ],
            ),
            html.Hr(style={"border": "none", "borderTop": f"1px solid {C['border']}",
                           "margin": "0.8rem 0"}),
            html.Div(
                style={"display": "flex", "gap": "2.5rem", "flexWrap": "wrap"},
                children=[
                    metrica("Año de censo", str(anio)),
                    metrica("Población 0–14", f"{data['pob_0_14']:,}"),
                    metrica("Población 65+", f"{data['pob_65_mas']:,}"),
                    metrica(
                        "Índice de envejecimiento",
                        ie_texto,
                        color=ie_color,
                        tooltip="(pob. 65+) / (pob. 0–14) × 100. Valores > 100 indican más adultos mayores que niños.",
                    ),
                ],
            ),
        ],
    )


# ── Punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=8050)