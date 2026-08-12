"""Genera el icono de la aplicacion (assets/app.ico).

Icono sencillo: corazon/ecg sobre fondo azul, con linea de electrocardiograma
blanca y un pulso rojo. Se dibuja en 4x y se reduce para suavizar bordes.
"""

import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "app.ico"

W = 256
SIZE = (W, W)
SS = 4  # supermuestreo para anti-aliasing
S = W * SS


def _rounded_rect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _ecg_points(step: int) -> list:
    """Puntos de una onda PQRST estilizada centrada en el paso `step`."""
    x = [
        step - 46, step - 34, step - 22, step - 14, step - 4,
        step + 2, step + 10, step + 20, step + 30, step + 42,
    ]
    y = [
        0, 0, -18, 0, -46,
        22, -34, 0, -14, 0,
    ]
    return list(zip(x, y))


def main():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Fondo: cuadrado redondeado con degradado azul oscuro
    for i in range(S):
        t = i / S
        r = int(13 + t * 18)
        g = int(48 + t * 16)
        b = int(94 + t * 30)
        _rounded_rect(d, (0, i, S, i + 1), S // 8, (r, g, b, 255))

    # Linea del electrocardiograma (blanca, centrada)
    cy = S // 2
    d.line((S * 0.08, cy, S * 0.92, cy), fill=(255, 255, 255, 255), width=S // 48)

    pts = []
    for px, py in _ecg_points(S // 2):
        pts.append((px, cy + py * (S // 130)))

    # Primer trazo de la onda (mas grueso, sombra)
    d.line(pts, fill=(255, 255, 255, 230), width=S // 34, joint="curve")

    # Corazon en la esquina del pulso
    hx, hy = S * 0.30, S * 0.30
    hr = S * 0.075
    d.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=(220, 38, 38, 255))
    d.polygon(
        [(hx, hy + hr), (hx - hr * 0.55, hy), (hx, hy - hr), (hx + hr * 0.55, hy)],
        fill=(220, 38, 38, 255),
    )

    # Reducir con anti-aliasing y guardar multi-resolucion
    img = img.resize(SIZE, Image.LANCZOS)
    os.makedirs(OUT.parent, exist_ok=True)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(OUT, format="ICO", sizes=sizes)
    print(f"Icono generado: {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    sys.exit(main())
