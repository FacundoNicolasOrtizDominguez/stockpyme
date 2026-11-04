"""
interfaz/tema.py — Temas de color de STOCKPYME
==============================================
Tres temas a elegir:

  • morado : el aspecto original (Catppuccin Mocha, fondo violeta oscuro). Es el de por defecto.
  • oscuro : gris carbón neutro con acento azul.
  • claro  : fondo claro con acento violeta.

Uso en las ventanas:

    from interfaz import tema as T
    tk.Label(self, bg=T.BG, fg=T.FG)

IMPORTANTE: leer siempre `T.COLOR` DENTRO de los métodos (cuando se construye el widget) y no
al importar el módulo ni como valor por defecto de un parámetro; si no, al cambiar de tema
quedarían colores viejos.

La elección se guarda por PC en DATA_DIR/preferencias.json (archivo aparte de config_local.json
para no interferir con el asistente de configuración de red). Para forzar un tema al arrancar
(pruebas) se puede usar la variable de entorno STOCKPYME_TEMA=morado|oscuro|claro.
"""

import json
import os

from backend.config import DATA_DIR

ARCHIVO_PREFERENCIAS = os.path.join(DATA_DIR, "preferencias.json")

TEMA_POR_DEFECTO = "morado"
ORDEN = ("morado", "oscuro", "claro")
NOMBRES = {
    "morado": "Morado (original)",
    "oscuro": "Oscuro",
    "claro": "Claro",
}

# ──────────────────────────────────────────────────────────────────────
# PALETAS
#   BG            fondo de las ventanas
#   PANEL         cabeceras / paneles laterales (más oscuro o más claro que BG)
#   CARD          tarjetas, tablas, campos de texto
#   HOVER         botones neutros, cabecera de tablas, hover de tarjetas
#   SELECT        fila seleccionada / botón neutro presionado
#   FAINT         texto muy tenue (pie de página)
#   MUTED         texto secundario
#   FG            texto principal
#   ACCENT        color de marca (títulos, botón principal)
#   ACCENT_HOVER  acento al pasar el mouse
#   ON_ACCENT     texto sobre botones de color (acento, verde, rojo, azul, amarillo)
#   RED GREEN BLUE YELLOW PEACH MAROON TEAL   colores semánticos
#   ALERT_BG      fondo del banner de alerta de stock
# ──────────────────────────────────────────────────────────────────────
TEMAS = {
    # Aspecto original — NO modificar estos valores (son los que tenía el programa)
    "morado": {
        "BG": "#1e1e2e", "PANEL": "#181825", "CARD": "#313244",
        "HOVER": "#45475a", "SELECT": "#585b70",
        "FAINT": "#45475a", "MUTED": "#6c7086", "FG": "#cdd6f4",
        "ACCENT": "#cba6f7", "ACCENT_HOVER": "#b4befe", "ON_ACCENT": "#1e1e2e",
        "RED": "#f38ba8", "GREEN": "#a6e3a1", "BLUE": "#89b4fa", "YELLOW": "#f9e2af",
        "PEACH": "#fab387", "MAROON": "#eba0ac", "TEAL": "#94e2d5",
        "ALERT_BG": "#45172a",
    },
    "oscuro": {
        "BG": "#15171c", "PANEL": "#0e1014", "CARD": "#20232b",
        "HOVER": "#2f343f", "SELECT": "#3d4452",
        "FAINT": "#5a6270", "MUTED": "#8b93a3", "FG": "#e4e7ee",
        "ACCENT": "#5aa9ff", "ACCENT_HOVER": "#8cc2ff", "ON_ACCENT": "#0e1014",
        "RED": "#f0707a", "GREEN": "#5fd38d", "BLUE": "#4cc9f0", "YELLOW": "#f2c94c",
        "PEACH": "#f59e6c", "MAROON": "#f28b9b", "TEAL": "#4fd1c5",
        "ALERT_BG": "#3a1a20",
    },
    "claro": {
        "BG": "#f4f5f9", "PANEL": "#e3e6ef", "CARD": "#ffffff",
        "HOVER": "#d3d8e5", "SELECT": "#b9c2dc",
        "FAINT": "#8a90a8", "MUTED": "#5c6178", "FG": "#1e2030",
        "ACCENT": "#7c3aed", "ACCENT_HOVER": "#6d28d9", "ON_ACCENT": "#ffffff",
        "RED": "#c0173f", "GREEN": "#1f7a2e", "BLUE": "#1d5fd1", "YELLOW": "#a15c00",
        "PEACH": "#c2410c", "MAROON": "#b4234a", "TEAL": "#0f766e",
        "ALERT_BG": "#fde2e8",
    },
}

# Valores "vacíos" para que los editores/linters conozcan los nombres; aplicar() los rellena.
BG = PANEL = CARD = HOVER = SELECT = FAINT = MUTED = FG = ""
ACCENT = ACCENT_HOVER = ON_ACCENT = ""
RED = GREEN = BLUE = YELLOW = PEACH = MAROON = TEAL = ALERT_BG = ""

actual = TEMA_POR_DEFECTO   # nombre del tema en uso


def _leer_preferencia():
    nombre = (os.environ.get("STOCKPYME_TEMA") or "").strip().lower()
    if nombre in TEMAS:
        return nombre
    try:
        with open(ARCHIVO_PREFERENCIAS, encoding="utf-8") as f:
            nombre = str(json.load(f).get("tema", "")).strip().lower()
    except (OSError, ValueError, AttributeError):
        nombre = ""
    return nombre if nombre in TEMAS else TEMA_POR_DEFECTO


def _guardar_preferencia(nombre):
    try:
        try:
            with open(ARCHIVO_PREFERENCIAS, encoding="utf-8") as f:
                datos = json.load(f)
            if not isinstance(datos, dict):
                datos = {}
        except (OSError, ValueError):
            datos = {}
        datos["tema"] = nombre
        with open(ARCHIVO_PREFERENCIAS, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
    except OSError:
        pass   # si no se puede guardar, el tema igual se usa durante esta sesión


def aplicar(nombre, guardar=True):
    """Activa un tema (y lo recuerda para la próxima vez). Las ventanas nuevas ya lo usan."""
    global actual
    if nombre not in TEMAS:
        nombre = TEMA_POR_DEFECTO
    globals().update(TEMAS[nombre])
    actual = nombre
    if guardar:
        _guardar_preferencia(nombre)


def _nombre_tema_ttk():
    # "morado" usa el clam de siempre (idéntico al original); los otros, un tema derivado de clam
    return "clam" if actual == "morado" else f"stockpyme_{actual}"


def usar_tema_ttk(estilo):
    """
    Activa el tema ttk que corresponde al tema de color actual. Las ventanas la llaman en lugar
    de `estilo.theme_use("clam")`. Cada paleta tiene su propio tema ttk, así los estilos de una
    no se mezclan con los de otra al cambiar de tema durante la sesión.
    """
    nombre = _nombre_tema_ttk()
    if nombre in estilo.theme_names():
        estilo.theme_use(nombre)
        return
    estilo.theme_create(nombre, parent="clam")
    estilo.theme_use(nombre)
    estilo.configure(
        "TCombobox", fieldbackground=CARD, background=HOVER, foreground=FG,
        arrowcolor=FG, bordercolor=HOVER, lightcolor=CARD, darkcolor=CARD,
        selectbackground=CARD, selectforeground=FG,
    )
    estilo.map(
        "TCombobox",
        fieldbackground=[("readonly", CARD), ("disabled", PANEL)],
        foreground=[("readonly", FG), ("disabled", MUTED)],
        selectbackground=[("readonly", CARD)],
        selectforeground=[("readonly", FG)],
    )
    for orient in ("Vertical", "Horizontal"):
        estilo.configure(
            f"{orient}.TScrollbar", background=HOVER, troughcolor=PANEL, bordercolor=PANEL,
            arrowcolor=FG, lightcolor=HOVER, darkcolor=HOVER,
        )


def configurar_ttk(widget):
    """
    Deja listo el estilo ttk del tema actual (combobox, scrollbars, tablas…). Llamar desde el
    constructor de las ventanas principales (login y principal), antes de crear widgets ttk.
    """
    from tkinter import ttk
    usar_tema_ttk(ttk.Style(widget))
    # Lista desplegable del combobox: es un Listbox de Tk, no de ttk
    widget.option_clear()
    if actual != "morado":
        widget.option_add("*TCombobox*Listbox.background", CARD)
        widget.option_add("*TCombobox*Listbox.foreground", FG)
        widget.option_add("*TCombobox*Listbox.selectBackground", SELECT)
        widget.option_add("*TCombobox*Listbox.selectForeground", FG)


aplicar(_leer_preferencia(), guardar=False)
