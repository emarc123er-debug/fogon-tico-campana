"""Genera static/promo-navidad.png (1080x1350, formato Instagram 4:5).

Solo usa datos fijos de la oferta (config.py). Las mesas libres de cada día
van en el texto del post, que Claude arma con datos reales del MCP.

Uso (requiere Pillow, solo para desarrollo):  python -m scripts.make_promo
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app import config

W, H = 1080, 1350
CREMA, ROJO, AMARILLO, VERDE, CAFE = "#FBF3E4", "#B3261E", "#F2B705", "#1F6B3A", "#3B2314"
FONTS = Path("C:/Windows/Fonts")


def fuente(nombre, tam):
    try:
        return ImageFont.truetype(str(FONTS / nombre), tam)
    except OSError:
        return ImageFont.load_default(tam)


def centrado(d, y, texto, f, color):
    w = d.textlength(texto, font=f)
    d.text(((W - w) / 2, y), texto, font=f, fill=color)


def franja(d, y, alto):
    """Franja de rombos estilo carreta típica."""
    d.rectangle([0, y, W, y + alto], fill=ROJO)
    paso = alto
    for i, x in enumerate(range(0, W + paso, paso)):
        c = AMARILLO if i % 2 == 0 else VERDE
        m = alto // 2
        d.polygon([(x, y + m), (x + m, y + 6), (x + paso, y + m), (x + m, y + alto - 6)], fill=c)
        d.ellipse([x + m - 7, y + m - 7, x + m + 7, y + m + 7], fill=CREMA)


def main():
    img = Image.new("RGB", (W, H), CREMA)
    d = ImageDraw.Draw(img)
    franja(d, 0, 70)
    franja(d, H - 70, 70)

    o = config.OFERTA
    centrado(d, 120, config.NEGOCIO.upper(), fuente("segoeuib.ttf", 40), VERDE)
    centrado(d, 185, "Cena Navideña", fuente("georgiab.ttf", 104), ROJO)
    centrado(d, 305, "Tica para 2", fuente("georgiab.ttf", 104), ROJO)

    # Precio ancla tachado + precio oferta
    f_ancla = fuente("segoeui.ttf", 56)
    ancla = f"Antes {config.colones(o['precio_ancla'])}"
    wa = d.textlength(ancla, font=f_ancla)
    xa, ya = (W - wa) / 2, 455
    d.text((xa, ya), ancla, font=f_ancla, fill=CAFE)
    d.line([(xa, ya + 36), (xa + wa, ya + 36)], fill=ROJO, width=6)

    d.rounded_rectangle([170, 540, W - 170, 720], radius=40, fill=ROJO)
    # Segoe UI sí incluye el símbolo ₡ (Georgia no)
    centrado(d, 548, config.colones(o["precio_oferta"]), fuente("segoeuib.ttf", 128), CREMA)
    ahorro = round(100 * (1 - o["precio_oferta"] / o["precio_ancla"]))
    centrado(d, 740, f"por pareja  ·  ahorrá {ahorro}%", fuente("segoeuib.ttf", 44), VERDE)

    f_item = fuente("segoeui.ttf", 38)
    y = 830
    for item in o["incluye"]:
        centrado(d, y, "• " + item, f_item, CAFE)
        y += 54

    d.rounded_rectangle([110, 1125, W - 110, 1245], radius=26, fill=AMARILLO)
    centrado(d, 1138, f"Solo {config.MESAS_POR_DIA} mesas por día · Vie a Dom de diciembre",
             fuente("segoeuib.ttf", 36), CAFE)
    limite = config.fecha_bonita(config.FECHA_LIMITE)
    centrado(d, 1188, f"Reservá hasta el {limite}", fuente("segoeuib.ttf", 36), ROJO)

    out = Path(__file__).resolve().parent.parent / "static" / "promo-navidad.png"
    img.save(out, optimize=True)
    print(f"Imagen generada: {out}")


if __name__ == "__main__":
    main()
