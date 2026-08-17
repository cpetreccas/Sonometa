import os
import pymupdf  # Uso del paquete actualizado según el warning

# SVG de la goma de borrar en color blanco (#FFFFFF)
svg_code = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21" />
  <path d="M22 21H7" />
  <path d="m5 11 9 9" />
</svg>"""

# Asegurar que la carpeta assets existe
output_dir = "assets"
os.makedirs(output_dir, exist_ok=True)

# Abrir y renderizar el vector SVG
doc = pymupdf.open(stream=svg_code.encode("utf-8"), filetype="svg")
page = doc[0]

# Renderizar en PNG con transparencia activa
pix = page.get_pixmap(dpi=300, alpha=True)
output_path = os.path.join(output_dir, "broom_icon.png")
pix.save(output_path)

print(f"Icono generado correctamente en: {output_path}")