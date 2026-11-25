#!/usr/bin/env python3
"""Writes a neutral stand-in logo (samples/logo-test/your-logo.svg and .png) used to show and
test the --logo path: layered colours, white cut-outs, a stroke-only shape, a group transform."""
import os
from matplotlib.font_manager import FontProperties
from matplotlib.path import Path as MPath
from matplotlib.textpath import TextPath

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "samples", "logo-test")
FONT = FontProperties(fname=os.path.join(HERE, "..", "fonts", "Inter-ExtraBold.otf"))


def text_d(s, size, cx, cy):
    tp = TextPath((0, 0), s, size=size, prop=FONT)
    bb = tp.get_extents()
    ox, oy = cx - (bb.x0 + bb.x1) / 2, cy + (bb.y0 + bb.y1) / 2      # SVG y runs down
    d, i, v, c = [], 0, tp.vertices, tp.codes
    while i < len(v):
        code = c[i]
        P = lambda k: f"{v[k][0] + ox:.2f},{oy - v[k][1]:.2f}"
        if code == MPath.MOVETO:
            d.append("M" + P(i)); i += 1
        elif code == MPath.LINETO:
            d.append("L" + P(i)); i += 1
        elif code == MPath.CURVE3:
            d.append("Q" + P(i) + " " + P(i + 1)); i += 2
        elif code == MPath.CURVE4:
            d.append("C" + P(i) + " " + P(i + 1) + " " + P(i + 2)); i += 3
        else:
            d.append("Z"); i += 1
    return "".join(d)


svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <g transform="translate(100 100) scale(0.96) translate(-100 -100)">
    <circle cx="100" cy="100" r="96" fill="#1b1b1d"/>
    <circle cx="100" cy="100" r="84" fill="none" stroke="#ffffff" stroke-width="5"/>
    <path d="M100,28 L109,54 L137,54 L114,70 L123,96 L100,80 L77,96 L86,70 L63,54 L91,54 Z" fill="#f7931a"/>
    <path d="{text_d("YOUR", 30, 100, 118)}" fill="#ffffff"/>
    <path d="{text_d("LOGO", 30, 100, 152)}" fill="#ffffff"/>
  </g>
</svg>'''
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "your-logo.svg"), "w").write(svg)

from PIL import Image, ImageDraw, ImageFont
im = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.ellipse([12, 12, 588, 588], fill=(27, 27, 29, 255))
d.ellipse([48, 48, 552, 552], outline=(255, 255, 255, 255), width=14)
star = [(300, 84), (327, 162), (411, 162), (342, 210), (369, 288), (300, 240), (231, 288), (258, 210), (189, 162), (273, 162)]
d.polygon(star, fill=(247, 147, 26, 255))
f = ImageFont.truetype(os.path.join(HERE, "..", "fonts", "Inter-ExtraBold.otf"), 92)
d.text((300, 352), "YOUR", font=f, fill=(255, 255, 255, 255), anchor="mm")
d.text((300, 454), "LOGO", font=f, fill=(255, 255, 255, 255), anchor="mm")
im.save(os.path.join(OUT, "your-logo.png"))
print("wrote your-logo.svg, your-logo.png")
