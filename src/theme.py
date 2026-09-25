"""Constantes de tema visual de Sonometa: paleta, tipografía, radios y espaciado.

Fuente única de verdad para todos los paneles de la UI de escritorio (CustomTkinter/Tkinter).
Traduce a Tkinter las variables definidas en docs/Guía de estilos Sonometa.md (pensada
originalmente para la PWA web). Notas de traducción:
  - Superficies, bordes y textos secundarios son los de la PWA (web/css/styles.css:
    --bg-color, --surface-color, --border-color...), algo más claros que los de la
    guía, para que escritorio y móvil se vean iguales. Acentos, estados y texto
    principal son 1:1 con la guía (coinciden en ambas).
  - La guía pide la fuente 'Inter'; no está instalada ni empaquetada en este proyecto, así
    que se usa 'Segoe UI' (fuente nativa de Windows, visualmente cercana) como equivalente real.
  - Tkinter solo soporta pesos "normal"/"bold" (no existe SemiBold/Medium nativos); los pesos
    intermedios de la guía se aproximan a "bold".
"""

# ------------------------------------------------------------------
# Superficies base
# ------------------------------------------------------------------
BG_MAIN = "#1A1A1E"         # Fondo general de la aplicación (PWA --bg-color)
BG_CARD = "#24242A"         # Tarjetas, modales, barra lateral y paneles (PWA --surface-color)
BG_CARD_ZEBRA = "#1F1F24"   # Filas alternas de la grilla (PWA --row-even)
BG_CARD_HOVER = "#2E2E36"   # Hover para tarjetas y filas de lista (PWA --surface-hover)
BG_INPUT = "#2D2D35"        # Fondo de campos de entrada: inputs, entries, combos (PWA --input-bg)

# ------------------------------------------------------------------
# Bordes y divisores
# ------------------------------------------------------------------
BORDER_QUIET = "#363640"    # Líneas divisorias sutiles, bordes de tabla/tarjetas (PWA --border-color)
BORDER_FOCUS = "#4B4B58"    # Bordes para elementos enfocados o activos (PWA --border-highlight)

# ------------------------------------------------------------------
# Acentos de marca
# ------------------------------------------------------------------
PRIMARY = "#8B5CF6"         # Morado corporativo principal
PRIMARY_HOVER = "#7C3AED"   # Morado más oscuro para estado hover en botones
PRIMARY_LIGHT = "#A78BFA"   # Morado claro para texto activo, iconos y remixes

# ------------------------------------------------------------------
# Colores de texto
# ------------------------------------------------------------------
TEXT_MAIN = "#F4F4F5"       # Texto principal de alto contraste
TEXT_MUTED = "#B3B3AD"      # Texto secundario: artistas, cabeceras de tabla (PWA --text-muted)
TEXT_SUBTLE = "#8E8E96"     # Textos menores, placeholders, pie de página (PWA --text-subtle)
TEXT_ON_PRIMARY = "#FFFFFF"  # Blanco puro para texto sobre fondo PRIMARY (ej. fila seleccionada)

# ------------------------------------------------------------------
# Estados e indicadores
# ------------------------------------------------------------------
STATUS_SUCCESS = "#22C55E"  # Verde - completo / salud excelente
STATUS_WARNING = "#F59E0B"  # Ámbar - falta algún metadato secundario
STATUS_DANGER = "#EF4444"   # Rojo - falta metadato crítico
STATUS_DANGER_HOVER = "#450A0A"  # Fondo hover sutil para botones destructivos ("transparent" + hover rojizo)
STATUS_INFO = "#3B82F6"     # Azul - mensajes informativos neutros

# Iconos de show_themed_dialog: verde esmeralda propio para "acción completada",
# deliberadamente distinto de STATUS_SUCCESS (reservado a indicadores de salud/estado).
MODAL_ICON_SUCCESS = "#10B981"

# ------------------------------------------------------------------
# Colores complementarios de componentes (guía, sección 3)
# ------------------------------------------------------------------
TABLE_HEADER_BG = "#1B1B20"       # Cabecera de tabla
TABLE_HEADER_HOVER = "#272730"    # Cabecera de tabla en hover
ROW_SELECTED = "#2F2643"          # Fila / tarjeta seleccionada
CHIP_ACTIVE_BG = "#2D2342"        # Chip / píldora activa (p. ej. indicador de filtro)
LEGEND_TEXT = "#E4E4E7"           # Nombres en las leyendas de gráficos
DANGER_TEXT = "#F87171"           # Texto y borde de acciones de peligro (hover de "Limpiar")
DANGER_HOVER_BG = "#382729"       # rgba(239, 68, 68, 0.1) sobre BG_CARD

# ------------------------------------------------------------------
# Tipografía
# ------------------------------------------------------------------
FONT_FAMILY = "Segoe UI"

FONT_SIZE_KPI = 28
FONT_SIZE_H1 = 20
FONT_SIZE_H2 = 16
FONT_SIZE_BODY = 14
FONT_SIZE_BADGE = 12
FONT_SIZE_MICRO = 10

# ------------------------------------------------------------------
# Radios de esquina
# ------------------------------------------------------------------
RADIUS_CONTROL = 8          # Botones, inputs, combos, checkboxes
RADIUS_CARD = 12            # Tarjetas y paneles elevados

# ------------------------------------------------------------------
# Escala de espaciado (padding/gutters). Usar siempre uno de estos valores
# en vez de números sueltos para mantener un ritmo visual consistente.
# ------------------------------------------------------------------
SPACE_XXS = 2
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32

# Alias semánticos usados en tarjetas/paneles elevados (ver guía, sección 3: 16px o 20px)
PADDING_CARD_SM = SPACE_MD  # 16
PADDING_CARD_LG = 20


def font(size=FONT_SIZE_BODY, weight="normal", family=FONT_FAMILY):
    """Devuelve el dict de kwargs listo para pasar a ctk.CTkFont(**theme.font(...))."""
    return {"family": family, "size": size, "weight": weight}


def _bind_hover_style(button, on_enter, on_leave):
    """CustomTkinter solo cambia el fondo de un botón en hover; los cambios de texto
    y borde que pide la guía se aplican con <Enter>/<Leave> (add="+" para no pisar
    el hover propio de CTkButton)."""
    def _enter(_event=None):
        if str(button.cget("state")) != "disabled":
            button.configure(**on_enter)

    def _leave(_event=None):
        button.configure(**on_leave)

    button.bind("<Enter>", _enter, add="+")
    button.bind("<Leave>", _leave, add="+")


def style_secondary_button(button):
    """Botón secundario (guía 4.2): transparente, borde BORDER_QUIET y texto
    TEXT_MUTED; en hover, texto blanco y borde BORDER_FOCUS. Devuelve el botón."""
    rest = {"text_color": TEXT_MUTED, "border_color": BORDER_QUIET}
    button.configure(fg_color="transparent", border_width=1, hover=False, **rest)
    _bind_hover_style(button, {"text_color": TEXT_ON_PRIMARY, "border_color": BORDER_FOCUS}, rest)
    return button


def style_reset_button(button):
    """Botón de restablecer/limpiar (guía 4.2): igual que el secundario en reposo;
    en hover, texto y borde rojos sobre un fondo rojizo. El rojo solo aparece al
    pasar el ratón. Devuelve el botón."""
    rest = {"text_color": TEXT_MUTED, "border_color": BORDER_QUIET}
    button.configure(fg_color="transparent", border_width=1, hover=True, hover_color=DANGER_HOVER_BG, **rest)
    _bind_hover_style(button, {"text_color": DANGER_TEXT, "border_color": DANGER_TEXT}, rest)
    return button

