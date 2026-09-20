"""Constantes de tema visual de Sonometa: paleta, tipografía, radios y espaciado.

Fuente única de verdad para todos los paneles de la UI de escritorio (CustomTkinter/Tkinter).
Traduce a Tkinter las variables definidas en docs/Guía de estilos Sonometa.md (pensada
originalmente para la PWA web). Notas de traducción:
  - Los valores de color son 1:1 con la guía.
  - La guía pide la fuente 'Inter'; no está instalada ni empaquetada en este proyecto, así
    que se usa 'Segoe UI' (fuente nativa de Windows, visualmente cercana) como equivalente real.
  - Tkinter solo soporta pesos "normal"/"bold" (no existe SemiBold/Medium nativos); los pesos
    intermedios de la guía se aproximan a "bold".
"""

# ------------------------------------------------------------------
# Superficies base
# ------------------------------------------------------------------
BG_MAIN = "#121212"         # Fondo general de la aplicación (ventana raíz)
BG_CARD = "#18181B"         # Tarjetas, modales, barra lateral y paneles elevados
BG_CARD_HOVER = "#27272A"   # Hover para tarjetas y filas de lista
BG_INPUT = "#18181B"        # Fondo de campos de entrada (inputs, entries, combos)

# ------------------------------------------------------------------
# Bordes y divisores
# ------------------------------------------------------------------
BORDER_QUIET = "#27272A"    # Líneas divisorias sutiles, bordes de tabla/tarjetas
BORDER_FOCUS = "#3F3F46"    # Bordes para elementos enfocados o activos

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
TEXT_MUTED = "#A1A1AA"      # Texto secundario (artistas, cabeceras de tabla)
TEXT_SUBTLE = "#71717A"     # Textos secundarios menores, placeholders, pie de página

# ------------------------------------------------------------------
# Estados e indicadores
# ------------------------------------------------------------------
STATUS_SUCCESS = "#22C55E"  # Verde - completo / salud excelente
STATUS_WARNING = "#F59E0B"  # Ámbar - falta algún metadato secundario
STATUS_DANGER = "#EF4444"   # Rojo - falta metadato crítico
STATUS_DANGER_HOVER = "#450A0A"  # Fondo hover sutil para botones destructivos ("transparent" + hover rojizo)

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
# Espaciado estándar (padding interno de tarjetas/paneles)
# ------------------------------------------------------------------
PADDING_CARD_SM = 16
PADDING_CARD_LG = 20


def font(size=FONT_SIZE_BODY, weight="normal", family=FONT_FAMILY):
    """Devuelve el dict de kwargs listo para pasar a ctk.CTkFont(**theme.font(...))."""
    return {"family": family, "size": size, "weight": weight}
