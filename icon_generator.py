from PIL import Image, ImageDraw

def generar_logo_relleno_directo(input_path="logo_3.png", output_path="logo_2.png"):
    # 1. Cargar la imagen de origen
    img = Image.open(input_path).convert("RGBA")
    w, h = img.size

    # 2. Crear una máscara en blanco y negro de los píxeles claros (el borde del icono)
    mask = Image.new("L", (w, h), 0)
    for y in range(h):
        for x in range(w):
            r, g, b, a = img.getpixel((x, y))
            # Si el píxel es visible y claro, marcamos la pared
            if a > 30 and (r + g + b) // 3 > 100:
                mask.putpixel((x, y), 255)

    # 3. Rellenar de blanco el interior partiendo exactamente del centro del icono
    centro_x, centro_y = int(w * 0.50), int(h * 0.50)
    ImageDraw.floodfill(mask, (centro_x, centro_y), 255)

    # 4. Crear la imagen final con fondo transparente y relleno blanco
    img_final = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y in range(h):
        for x in range(w):
            if mask.getpixel((x, y)) == 255:
                img_final.putpixel((x, y), (255, 255, 255, 255))

    # 5. Vaciar el punto circular interior
    dot_x, dot_y = int(w * 0.72), int(h * 0.50)
    ImageDraw.floodfill(img_final, (dot_x, dot_y), (0, 0, 0, 0))

    img_final.save(output_path, "PNG")
    print(f"¡Generado correctamente en '{output_path}'!")

if __name__ == "__main__":
    generar_logo_relleno_directo()