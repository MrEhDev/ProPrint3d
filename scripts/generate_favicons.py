import os
from PIL import Image, ImageEnhance, ImageFilter

def make_favicons():
    src_path = "static/images/proprint3d_logo_transparent.png"
    if not os.path.exists(src_path):
        print(f"Error: {src_path} not found")
        return

    img = Image.open(src_path).convert("RGBA")
    
    # Obtener el bbox recortado sin espacio vacío
    bbox = img.getbbox()
    if bbox:
        img_cropped = img.crop(bbox)
    else:
        img_cropped = img

    w, h = img_cropped.size
    max_dim = max(w, h)
    
    # Crear un canvas cuadrado transparente con un pequeño margen (5%) para que respire
    pad = int(max_dim * 0.05)
    canvas_size = max_dim + 2 * pad
    square_canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    offset = ((canvas_size - w) // 2, (canvas_size - h) // 2)
    square_canvas.paste(img_cropped, offset, img_cropped)

    # Mejorar contraste y saturación para tamaños diminutos (16-48px)
    enh_color = ImageEnhance.Color(square_canvas)
    vibrant_canvas = enh_color.enhance(1.25)
    enh_contrast = ImageEnhance.Contrast(vibrant_canvas)
    vibrant_canvas = enh_contrast.enhance(1.2)
    enh_sharpness = ImageEnhance.Sharpness(vibrant_canvas)
    vibrant_canvas = enh_sharpness.enhance(1.4)

    # Generar tamaños estándar
    sizes = {
        "favicon-16x16.png": 16,
        "favicon-32x32.png": 32,
        "favicon-48x48.png": 48,
        "favicon-96x96.png": 96,
        "favicon-192x192.png": 192,
        "favicon-512x512.png": 512,
        "apple-touch-icon.png": 180,
        "favicon.png": 192,
    }

    images_for_ico = []
    for filename, size in sizes.items():
        resized = vibrant_canvas.resize((size, size), Image.Resampling.LANCZOS)
        out_path = os.path.join("static/images", filename)
        resized.save(out_path, "PNG", optimize=True)
        print(f"Guardado {out_path} ({size}x{size})")
        if size in (16, 32, 48):
            images_for_ico.append(resized)

    # Generar favicon.ico multi-resolución (16, 32, 48)
    ico_path = os.path.join("static/images", "favicon.ico")
    # Para ICO se recomienda guardar la lista de tamaños
    img_48 = vibrant_canvas.resize((48, 48), Image.Resampling.LANCZOS)
    img_48.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"Guardado {ico_path} multi-resolución (16, 32, 48)")

    # Versión con fondo oscuro #0f172a (favicon.jpg)
    dark_bg = Image.new("RGB", (180, 180), (15, 23, 42))
    render_resized = vibrant_canvas.resize((150, 150), Image.Resampling.LANCZOS)
    dark_bg.paste(render_resized, (15, 15), render_resized)
    dark_bg.save(os.path.join("static/images", "favicon.jpg"), "JPEG", quality=95)
    print("Guardado favicon.jpg con fondo oscuro")

if __name__ == "__main__":
    make_favicons()

