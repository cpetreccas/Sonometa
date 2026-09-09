import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

class SVGConverter:
    def __init__(self, svg_path: str):
        self.svg_path = Path(svg_path).resolve()
        if not self.svg_path.exists():
            raise FileNotFoundError(f"Error: El archivo '{self.svg_path}' no existe.")

    def trim_transparency(self, image_path: Path):
        """Recorta automáticamente los márgenes transparentes alrededor del logo."""
        with Image.open(image_path) as img:
            img = img.convert("RGBA")
            # Obtener la caja delimitadora de los píxeles no transparentes
            bbox = img.getbbox()
            if bbox:
                cropped = img.crop(bbox)
                cropped.save(image_path)

    def to_png(self, output_path: str = None, scale: float = 3.0) -> str:
        if output_path is None:
            output_path = self.svg_path.with_suffix('.png')
        else:
            output_path = Path(output_path).resolve()

        svg_content = self.svg_path.read_text(encoding="utf-8")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Usamos un viewport grande para capturar con máxima resolución
            page = browser.new_page(
                viewport={"width": 1200, "height": 400},
                device_scale_factor=scale
            )

            html_document = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    html, body {{
                        margin: 0;
                        padding: 0;
                        background: transparent !important;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        width: 100vw;
                        height: 100vh;
                        overflow: hidden;
                    }}
                    svg {{
                        max-width: 100%;
                        max-height: 100%;
                    }}
                </style>
            </head>
            <body>
                {svg_content}
            </body>
            </html>
            """

            page.set_content(html_document)
            page.screenshot(path=str(output_path), omit_background=True)
            browser.close()

        # Recortar automáticamente para ajustar al marco exacto del logo original
        self.trim_transparency(output_path)

        print(f"✅ PNG ajustado perfectamente al encuadre original en: {output_path}")
        return str(output_path)


if __name__ == "__main__":
    archivo_svg = sys.argv[1] if len(sys.argv) > 1 else "logo_completo.svg"

    try:
        converter = SVGConverter(archivo_svg)
        converter.to_png()
    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")