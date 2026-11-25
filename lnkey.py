#!/usr/bin/env python3
"""
lnkey - Lightning-address keychain generator for the Bambu Lab A1 + AMS lite.

Turns a Lightning address (name@wallet.com) into a ready-to-print, multi-colour
Bambu Studio project (.3mf): QR on one side, an icon / logo / text on the other.

    python lnkey.py jasonbohio@blink.sv --edition retail --back coffee -o out/

Editions (presets - every setting can be overridden):
    meetup   relief QR, 2 colours, colour changes by height only (cheapest, fastest)
    retail   flush QR face-down on the plate, double-sided, up to 4 colours
    ekasi    the Bitcoin Ekasi look (raised rim + raised QR) with their logo on the back

Run `python lnkey.py --help` for everything else, `--list-icons coffee` to search icons.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import zipfile
from dataclasses import dataclass, field, asdict

import numpy as np
import segno
from manifold3d import CrossSection, FillRule, Manifold
from shapely import affinity
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(HERE, "icons")
FONT_BOLD = os.path.join(HERE, "fonts", "Inter-ExtraBold.otf")     # heavy strokes print cleanly
FONT_NARROW = os.path.join(HERE, "fonts", "LiberationSansNarrow-Bold.ttf")

LAYER = 0.2          # layer height the designs are built around (mm)
# Per-object slicer settings written into the project. A tag is small and takes knocks on a key
# ring, so it prints solid: five walls and 100% infill leave no sparse core in the loop or behind
# the code (a sparse core also shows through light plastic as a shadow pattern).
PRINT_SETTINGS = {"wall_loops": "5", "sparse_infill_density": "100%", "top_shell_layers": "5",
                  "bottom_shell_layers": "5"}
PLA_DENSITY = 1.24   # g/cm3
BED = 256.0          # A1 build plate (mm)

# ----------------------------------------------------------------------------
# Colourways.  Slot numbers are AMS lite positions (filament 1-4 in Bambu Studio).
# body  = the bulk of the tag          field = the light colour behind the QR
# ink   = the dark QR modules / text   accent = the icon on the back
# ----------------------------------------------------------------------------
COLORS = {
    "white": "#F4F4F0", "black": "#1B1B1D", "orange": "#F7931A", "yellow": "#F5C518",
    "red": "#C8102E", "blue": "#0A5EB0", "navy": "#14213D", "green": "#1E8E4A",
    "teal": "#0E9AA7", "purple": "#6A3FA0", "pink": "#F06292", "gray": "#8E9196",
    "brown": "#6B4226", "gold": "#C9A227", "cream": "#EFE6D0", "mint": "#A8E0C8",
}
LIGHT = ("white", "cream", "yellow", "mint")       # colours that need extra layers to cover a dark one
COLORWAYS = {
    #            body      field     ink      accent
    "classic":  ("white",  "white",  "black", "orange"),
    "ekasi":    ("white",  "white",  "black", "black"),
    "bitcoin":  ("orange", "orange", "black", "white"),
    "midnight": ("black",  "white",  "black", "orange"),
    "ohio":     ("white",  "white",  "navy",  "red"),
    "cafe":     ("cream",  "cream",  "brown", "orange"),
    "forest":   ("white",  "white",  "green", "gold"),
    "ocean":    ("white",  "white",  "navy",  "teal"),
    "sunny":    ("yellow", "yellow", "black", "red"),
    "mono":     ("white",  "white",  "black", "black"),
}

# Friendly names for a curated set of back-side icons (any of the 7,400+
# Material Design Icons file names in ./icons also works, e.g. --back trumpet).
ICON_ALIASES = {
    # hospitality / tips
    "coffee": "coffee", "barista": "coffee-to-go", "tea": "tea", "bartender": "glass-cocktail",
    "beer": "glass-mug-variant", "wine": "glass-wine", "server": "silverware-fork-knife",
    "chef": "chef-hat", "pizza": "pizza", "taco": "taco", "burger": "hamburger",
    "icecream": "ice-cream", "bakery": "cupcake", "bread": "baguette", "foodtruck": "food-truck" ,
    "bbq": "grill",
    # trades & services
    "barber": "content-cut", "salon": "hair-dryer", "nails": "bottle-tonic",
    "mechanic": "toolbox", "handyman": "hammer-wrench", "carwash": "car-wash", "driver": "car-side",
    "delivery": "moped", "bike": "bicycle", "cleaning": "broom", "lawn": "mower",
    "plumber": "pipe-wrench", "electrician": "flash", "photo": "camera", "dogwalker": "dog-side",
    "pets": "paw", "babysitter": "baby-carriage", "tutor": "school", "fitness": "dumbbell",
    "yoga": "yoga", "massage": "spa", "florist": "flower-tulip",
    "printing": "printer-3d-nozzle", "it": "laptop", "realtor": "home-city",
    # makers / farm / market
    "eggs": "egg", "farm": "barn", "tractor": "tractor", "honey": "bee", "produce": "carrot",
    "corn": "corn", "market": "storefront", "thrift": "hanger", "books": "book-open-variant",
    "art": "palette", "pottery": "pot-mix", "candle": "candle",
    # music & arts
    "music": "music", "guitar": "guitar-acoustic", "electric": "guitar-electric", "trumpet": "trumpet",
    "trombone": "trombone", "sax": "saxophone", "piano": "piano", "violin": "violin", "drums": "music-clef-bass",
    "mic": "microphone-variant", "dj": "headphones", "vinyl": "album", "theater": "drama-masks",
    # interests
    "heart": "heart", "star": "star", "smile": "emoticon-happy", "peace": "peace", "cross": "cross",
    "church": "church", "chess": "chess-knight", "hiking": "hiking", "tent": "tent", "tree": "pine-tree",
    "mountain": "image-filter-hdr", "fishing": "fish", "surf": "surfing", "waves": "waves",
    "gaming": "controller", "dice": "dice-5", "rocket": "rocket-launch", "robot": "robot",
    "football": "football", "baseball": "baseball", "basketball": "basketball", "soccer": "soccer",
    "golf": "golf", "bowling": "bowling", "skate": "skateboard", "anchor": "anchor",
    # bitcoin
    "btc": "bitcoin-coin", "bitcoin": "bitcoin-coin", "b": "bitcoin", "bolt": "lightning-bolt", "sats": "sats",
    "pill": "orange-pill", "zap": "zap-coin", "tipjar": "tip-jar", "miner": "home-miner", "asic": "asic-miner", "s9": "asic-miner", "tips": "hand-coin", "piggy": "piggy-bank",
    "giving": "hand-heart", "key": "key-variant", "shield": "shield-check", "pickaxe": "pickaxe",
    "node": "server", "wallet": "wallet",
}


# ----------------------------------------------------------------------------
# 2-D helpers
# ----------------------------------------------------------------------------
def disc(r, cx=0.0, cy=0.0):
    return Point(cx, cy).buffer(r, quad_segs=48)


def rounded_square(side, r):
    return box(-side / 2 + r, -side / 2 + r, side / 2 - r, side / 2 - r).buffer(r, quad_segs=24)


def polys(geom):
    """Flatten any shapely geometry to a list of Polygons."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    out = []
    for g in getattr(geom, "geoms", []):
        out.extend(polys(g))
    return out


def clean(geom, min_area=0.02):
    ps = [p for p in polys(geom.buffer(0)) if p.area >= min_area]
    return unary_union(ps) if ps else Polygon()


def mirror_x(geom):
    return affinity.scale(geom, xfact=-1, yfact=1, origin=(0, 0))


def rings_to_shape(rings):
    """Closed rings (font / SVG sub-paths) -> shape, by the non-zero fill rule.

    Every face of the arrangement of rings is kept when its winding number is not zero, which is
    what SVG and font renderers do. (Going by ring orientation alone gets shapes such as the
    Bitcoin mark wrong: its two counters are drawn in opposite directions.)
    """
    from shapely.ops import polygonize
    items = []
    for r in rings:
        r = np.asarray(r, float)
        if len(r) < 4:
            continue
        p = Polygon(r)
        if p.area < 1e-9:
            continue
        x, y = r[:, 0], r[:, 1]
        signed = 0.5 * float(np.sum(x[:-1] * y[1:] - x[1:] * y[:-1]))
        items.append((1 if signed > 0 else -1, p.buffer(0)))
    if not items:
        return Polygon()
    if len(items) == 1:
        return items[0][1]
    lines = unary_union([p.boundary for _, p in items])
    keep = []
    for face in polygonize(lines):
        pt = face.representative_point()
        if sum(sign for sign, p in items if p.contains(pt)) != 0:
            keep.append(face)
    return unary_union(keep) if keep else Polygon()


# ----------------------------------------------------------------------------
# Icons (SVG paths) and text (font outlines)
# ----------------------------------------------------------------------------
_icon_cache = {}


def _sample_path(d, transform=None):
    from svgelements import Arc, Close, CubicBezier, Line, Move, Path, QuadraticBezier
    path = Path(d)
    if transform is not None:
        path = path * transform
        path.reify()
    rings = []
    for sub in path.as_subpaths():
        pts = []
        for seg in Path(sub):
            if isinstance(seg, Move):
                continue
            if isinstance(seg, (Line, Close)):
                if seg.start is not None and not pts:
                    pts.append((seg.start.x, seg.start.y))
                if seg.end is not None:
                    pts.append((seg.end.x, seg.end.y))
            elif isinstance(seg, (CubicBezier, QuadraticBezier, Arc)):
                n = 16
                for i in range(n + 1):
                    p = seg.point(i / n)
                    pts.append((p.x, p.y))
        if len(pts) >= 3:
            if pts[0] != pts[-1]:
                pts.append(pts[0])
            rings.append(pts)
    return rings


def load_svg(path):
    """Filled shapes of an SVG file -> shapely geometry (y up, centred, unit height)."""
    from svgelements import SVG, Shape, Path as SPath
    rings = []
    svg = SVG.parse(path, reify=True)
    for el in svg.elements():
        if isinstance(el, Shape):
            fill = getattr(el, "fill", None)
            if fill is not None and getattr(fill, "value", 1) is None:
                continue  # fill="none"
            rings.extend(_sample_path(SPath(el).d()))
    shape = rings_to_shape(rings)
    if shape.is_empty:
        raise ValueError(f"no filled shapes found in {path}")
    shape = affinity.scale(shape, 1, -1, origin=(0, 0))        # SVG y is down
    minx, miny, maxx, maxy = shape.bounds
    shape = affinity.translate(shape, -(minx + maxx) / 2, -(miny + maxy) / 2)
    s = 1.0 / max(maxx - minx, maxy - miny)
    return affinity.scale(shape, s, s, origin=(0, 0))


def _lum(rgb):
    r, g, b = [c / 255.0 for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _hex(c):
    c = COLORS.get(c, c)
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _svg_layers(path, notes):
    """Every painted shape of an SVG, in paint order: [(rgb or None, geometry)], y up."""
    from svgelements import SVG, Shape, Path as SPath, SVGText, SVGImage
    from shapely.geometry import LineString
    layers = []
    svg = SVG.parse(path, reify=True)
    for el in svg.elements():
        if isinstance(el, SVGText):
            notes.append("the SVG contains live text - convert text to outlines so it prints")
            continue
        if isinstance(el, SVGImage):
            notes.append("the SVG embeds a picture - only vector shapes are used")
            continue
        if not isinstance(el, Shape):
            continue
        try:
            rings = _sample_path(SPath(el).d())
        except Exception:
            continue
        fill, stroke = getattr(el, "fill", None), getattr(el, "stroke", None)

        def rgb_of(paint):
            try:
                if paint is None or paint.value is None:
                    return "none"
                if getattr(paint, "opacity", 1.0) is not None and paint.opacity < 0.05:
                    return "none"
                return (int(paint.red), int(paint.green), int(paint.blue))
            except Exception:
                return None                                   # gradients and patterns: treat as dark

        f = rgb_of(fill)
        if f != "none" and rings:
            evenodd = str(getattr(el, "values", {}).get("fill-rule", "")).lower() == "evenodd"
            if evenodd:
                geom = Polygon()
                for r in rings:
                    if len(r) >= 4:
                        geom = geom.symmetric_difference(Polygon(r).buffer(0))
            else:
                geom = rings_to_shape(rings)
            if not geom.is_empty:
                layers.append((f, affinity.scale(geom, 1, -1, origin=(0, 0))))
        st = rgb_of(stroke)
        try:
            w = float(getattr(el, "implicit_stroke_width", None) or el.stroke_width or 0)
        except Exception:
            w = 0.0
        if st != "none" and stroke is not None and w > 0 and rings:
            lines = [LineString(r).buffer(w / 2, cap_style="round", join_style="round") for r in rings if len(r) >= 2]
            geom = unary_union(lines)
            if not geom.is_empty:
                layers.append((st, affinity.scale(geom, 1, -1, origin=(0, 0))))
    return layers


def _raster_layers(path, mode, palette, notes):
    """Trace a PNG/JPG: one layer per colour role. Returns [(role, geometry)], y up."""
    import cv2
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    k = max(1.0, 1200 / max(im.size))
    if k > 1:
        im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32)
    rgb, alpha = a[..., :3], a[..., 3]
    has_alpha = bool((alpha < 128).mean() > 0.01)
    opaque = alpha >= 128
    lum = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]) / 255.0
    masks = {}
    if mode == "color":
        roles = list(palette)
        d = np.stack([((rgb - np.array(palette[r], np.float32)) ** 2).sum(-1) for r in roles], -1)
        near = d.argmin(-1)
        for i, r in enumerate(roles):
            if r != "field":
                masks[r] = opaque & (near == i)
    else:
        dark = opaque & (lum < (0.8 if has_alpha else 0.6))
        if dark.mean() < 0.005 and has_alpha:               # an all-light logo on transparency: use its shape
            dark = opaque
            notes.append("logo is light-on-transparent: using its outline shape as the dark colour")
        masks["ink"] = dark
    out, H = [], a.shape[0]
    for role, m in masks.items():
        m8 = (m.astype(np.uint8)) * 255
        m8 = cv2.medianBlur(m8, 5)
        contours, hier = cv2.findContours(m8, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        polys_ = []
        if hier is not None:
            for i, c in enumerate(contours):
                if hier[0][i][3] != -1 or len(c) < 4:
                    continue
                holes, j = [], hier[0][i][2]
                while j != -1:
                    if len(contours[j]) >= 4:
                        holes.append([(float(x), float(H - y)) for [[x, y]] in contours[j]])
                    j = hier[0][j][0]
                p = Polygon([(float(x), float(H - y)) for [[x, y]] in c], holes).buffer(0)
                if p.area > 12:
                    polys_.append(p)
        if polys_:
            out.append((role, unary_union(polys_).simplify(0.7).buffer(1.2).buffer(-1.2)))
    return out


def load_art(path, mode="mono", palette=None):
    """A customer's logo file -> {'ink': geom, 'accent': geom}, centred, larger side = 1.

    mode 'mono'  : dark shapes print in the ink colour; white shapes cut holes (paint order respected)
    mode 'color' : every colour goes to the nearest of the colourway's field / ink / accent filaments
    """
    notes = []
    palette = palette or {"field": (244, 244, 240), "ink": (27, 27, 29), "accent": (247, 147, 26)}
    regions = {"ink": Polygon(), "accent": Polygon()}
    if path.lower().endswith(".svg"):
        layers = _svg_layers(path, notes)
        if not layers:
            raise SystemExit(f"no drawable shapes found in {path}")
        painted = []
        for rgb, geom in layers:
            if rgb is None:
                role = "ink"
            elif mode == "color":
                role = min(palette, key=lambda r: sum((a - b) ** 2 for a, b in zip(rgb, palette[r])))
            else:
                role = "field" if _lum(rgb) > 0.8 else "ink"
            painted.append((role, geom))
        if mode != "color" and all(r == "field" for r, _ in painted):
            painted = [("ink", g) for _, g in painted]
            notes.append("logo is drawn in white only: printing its shapes in the dark colour")
        for role, geom in painted:                          # later shapes sit on top of earlier ones
            for k in regions:
                if k != role and not regions[k].is_empty:
                    regions[k] = regions[k].difference(geom)
            if role in regions:
                regions[role] = regions[role].union(geom)
    else:
        for role, geom in _raster_layers(path, mode, palette, notes):
            regions[role] = geom
    whole = unary_union(list(regions.values()))
    if whole.is_empty:
        raise SystemExit(f"nothing printable found in {path}")
    minx, miny, maxx, maxy = whole.bounds
    k = 1.0 / max(maxx - minx, maxy - miny)
    for r in regions:
        g = affinity.translate(regions[r], -(minx + maxx) / 2, -(miny + maxy) / 2)
        regions[r] = affinity.scale(g, k, k, origin=(0, 0)).buffer(0)
    return regions, notes


def resolve_icon(name):
    if not name or name == "none":
        return None
    if os.path.isfile(name):
        return name
    key = ICON_ALIASES.get(name.lower(), name.lower())
    path = os.path.join(ICON_DIR, key + ".svg")
    if not os.path.isfile(path):
        hits = search_icons(name)[:12]
        raise SystemExit(f"icon '{name}' not found. Close matches: {', '.join(hits) or 'none'}\n"
                         f"Try: python lnkey.py --list-icons {name}")
    return path


def icon(name):
    """Icon as a shape centred on the origin whose larger side is 1.0."""
    path = resolve_icon(name)
    if path is None:
        return None
    if path not in _icon_cache:
        _icon_cache[path] = load_svg(path)
    return _icon_cache[path]


def search_icons(term=""):
    term = term.lower()
    names = sorted(f[:-4] for f in os.listdir(ICON_DIR) if f.endswith(".svg"))
    alias = sorted(k for k in ICON_ALIASES if term in k)
    return alias + [n for n in names if term in n and not n.endswith("-outline")]


_font_cache = {}


def _font(path):
    if path not in _font_cache:
        from matplotlib.font_manager import FontProperties
        from matplotlib.textpath import TextPath
        fp = FontProperties(fname=path)
        h = TextPath((0, 0), "H", size=100, prop=fp).get_extents()
        _font_cache[path] = (fp, (h.y1 - h.y0) / 100.0)
    return _font_cache[path]


def glyph(ch, font_path, cap):
    """(shape with baseline at y=0 and left edge of its advance box at x=0, advance)."""
    if ch in "⚡₿":
        ic = icon("flash" if ch == "⚡" else "bitcoin")       # "flash" is the chunkiest bolt in the set
        h = cap * 1.5
        minx, miny, maxx, maxy = ic.bounds
        g = affinity.scale(ic, h / (maxy - miny), h / (maxy - miny), origin=(0, 0))
        minx, miny, maxx, maxy = g.bounds
        g = affinity.translate(g, -minx + cap * 0.05, -miny - cap * 0.25)
        return g, (maxx - minx) + cap * 0.10
    from matplotlib.textpath import TextPath, TextToPath
    fp, cap_ratio = _font(font_path)
    size = cap / cap_ratio
    fp2 = fp.copy()
    fp2.set_size(size)
    adv = TextToPath().get_text_width_height_descent(ch, fp2, ismath=False)[0]
    if ch == " ":
        return Polygon(), adv
    tp = TextPath((0, 0), ch, size=size, prop=fp)
    return rings_to_shape(tp.to_polygons(closed_only=True)), adv


def text_line(s, cap, font_path=FONT_BOLD, tracking=0.05):
    """Straight line of text centred on the origin (vertically centred on the caps)."""
    parts, x = [], 0.0
    for ch in s:
        g, adv = glyph(ch, font_path, cap)
        if not g.is_empty:
            parts.append(affinity.translate(g, x, 0))
        x += adv + tracking * cap
    width = x - tracking * cap
    geom = unary_union(parts) if parts else Polygon()
    return affinity.translate(geom, -width / 2, -cap / 2), width


def fit_line(s, max_width, cap, min_cap=2.0):
    """Largest text that fits max_width: bold first, then the narrow face."""
    for font in (FONT_BOLD, FONT_NARROW):
        g, w = text_line(s, cap, font)
        if w <= max_width:
            return g, cap, font
        c2 = cap * max_width / w
        if c2 >= (2.5 if font == FONT_BOLD else min_cap):
            return text_line(s, c2, font)[0], c2, font
    c2 = max(min_cap, cap * max_width / w)
    return text_line(s, c2, FONT_NARROW)[0], c2, FONT_NARROW


def arc_text(s, cap, r_mid, top=True, max_half_angle=math.radians(75),
             font_path=FONT_BOLD, tracking=0.06, min_cap=2.0):
    """Text on a circle of radius r_mid (through mid cap-height), centred at 12 or 6 o'clock.
    Shrinks (and switches to the narrow face) so it stays within +-max_half_angle."""
    def measure(c, font):
        gl = [glyph(ch, font, c) for ch in s]
        return gl, sum(a for _, a in gl) + tracking * c * (len(s) - 1)

    limit = 2 * max_half_angle * r_mid
    font = font_path
    gl, total = measure(cap, font)
    if total > limit:
        c2 = cap * limit / total
        if c2 < 2.5 and font != FONT_NARROW:
            font = FONT_NARROW
            gl, total = measure(cap, font)
            c2 = min(cap, cap * limit / total)
        cap = max(min_cap, c2)
        gl, total = measure(cap, font)
    parts, x = [], -total / 2
    for g, adv in gl:
        if not g.is_empty:
            theta = (x + adv / 2) / r_mid
            g = affinity.translate(g, -adv / 2, 0)
            if top:
                g = affinity.translate(g, 0, r_mid - cap / 2)
                g = affinity.rotate(g, -math.degrees(theta), origin=(0, 0))
            else:
                g = affinity.translate(g, 0, -(r_mid + cap / 2))
                g = affinity.rotate(g, math.degrees(theta), origin=(0, 0))
            parts.append(g)
        x += adv + tracking * cap
    return (unary_union(parts) if parts else Polygon()), cap, total / r_mid / 2


# ----------------------------------------------------------------------------
# QR
# ----------------------------------------------------------------------------
BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _bech32_polymod(values):
    gen = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1ffffff) << 5 ^ v
        for i in range(5):
            chk ^= gen[i] if ((b >> i) & 1) else 0
    return chk


def lnurl_encode(url):
    hrp = "lnurl"
    acc, bits, data = 0, 0, []
    for byte in url.encode():
        acc = (acc << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            data.append((acc >> bits) & 31)
    if bits:
        data.append((acc << (5 - bits)) & 31)
    hrp_exp = [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]
    pm = _bech32_polymod(hrp_exp + data + [0] * 6) ^ 1
    data += [(pm >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(BECH32[d] for d in data)


def qr_payload(address, mode="uri"):
    """What the QR actually says.
    uri    lightning:name@domain   (default - opens a wallet from a phone camera, smallest code)
    plain  name@domain             (smallest; phone cameras treat it as an e-mail address)
    lnurl  LIGHTNING:LNURL1...     (classic LNURL-pay; widest wallet support, denser code)
    raw    use the text exactly as given (any URL / text)
    """
    if mode == "raw":
        return address
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", address):
        raise SystemExit(f"'{address}' does not look like a Lightning address (name@domain)")
    address = address.lower()
    if mode == "plain":
        return address
    if mode == "lnurl":
        user, domain = address.split("@")
        return "LIGHTNING:" + lnurl_encode(f"https://{domain}/.well-known/lnurlp/{user}").upper()
    return "lightning:" + address


def qr_matrix(payload, error=None):
    """Smallest standard QR for the payload, then the highest error correction that still fits."""
    if error:
        qr = segno.make(payload, error=error, micro=False, boost_error=False)
    else:
        qr = segno.make(payload, error="m", micro=False, boost_error=True)
    m = np.array([[1 if c else 0 for c in row] for row in qr.matrix], dtype=np.uint8)
    return m, qr


def qr_shape(matrix, module, shrink=0.04):
    """Dark modules as one geometry centred on the origin (row 0 at the top)."""
    n = matrix.shape[0]
    half = n * module / 2
    boxes = []
    for r in range(n):
        c = 0
        while c < n:
            if matrix[r, c]:
                c0 = c
                while c < n and matrix[r, c]:
                    c += 1
                boxes.append(box(-half + c0 * module, half - (r + 1) * module,
                                 -half + c * module, half - r * module))
            else:
                c += 1
    dark = unary_union(boxes)
    # pull dark edges in a hair: compensates ink spread and separates corner-touching modules
    # shrink > 0 pulls dark edges in, shrink < 0 pushes them out. Either way modules that only
    # touch at a corner end up cleanly separate or cleanly joined, never meeting at a single point.
    if abs(shrink) < 0.005:
        shrink = -0.01
    return dark.buffer(-shrink, join_style="mitre")


# ----------------------------------------------------------------------------
# Design spec
# ----------------------------------------------------------------------------
@dataclass
class Spec:
    address: str
    payload_mode: str = "uri"
    edition: str = "retail"
    shape: str = "round"            # round | square
    style: str = "flush"            # flush (QR face-down, flat) | relief (QR raised, face-up)
    colorway: str = "classic"
    module: float = 1.0             # QR module size (mm) - keep >= 0.9 on a 0.4 nozzle
    error: str | None = None        # force QR error correction (l/m/q/h)
    invert: bool = False            # light modules on a dark field (the Milani look) - scans less reliably
    thickness: float = 3.0          # flush style total thickness
    base: float = 2.2               # relief style base thickness
    relief: float = 0.4             # relief style module height (2 layers)
    rim: float = 1.8                # rim width
    rim_extra: float = 0.2          # relief style: rim stands this much above the modules
    inlay: float = 0.6              # colour inlay depth on flush faces (3 layers)
    back: str = "btc"               # icon name / svg path / "none"
    logo: str = ""                  # a logo file (.svg, .png, .jpg) for the back; replaces the icon
    logo_mode: str = "mono"         # mono: one dark colour | color: map the logo's colours to filaments
    logo_scale: float = 1.0         # shrink (<1) or grow (>1) the logo within its space
    logo_bleed: bool = False        # a round badge logo: run it to the edge so the back IS the badge
    back_top: str = ""
    back_bottom: str | None = None  # optional words under the image (off by default)
    back_lines: list = field(default_factory=list)  # text-only back (replaces the icon)
    back_rim: bool = True
    nfc: bool = False               # 26 mm pocket for an NTAG sticker (flush style)
    tab: bool = True
    hole: float = 5.0               # key-ring hole diameter
    dark_comp: float | None = None  # mm added to every dark QR edge (None = tuned default per style)
    loop_wall: float = 3.0          # plastic around the hole (the part that used to snap)
    loop_fillet: float = 3.5        # radius blending the loop into the tag
    name: str = ""

    def colours(self):
        return dict(zip(("body", "field", "ink", "accent"), COLORWAYS[self.colorway]))


EDITIONS = {
    "meetup": dict(style="relief", colorway="mono", back="none", back_bottom="", back_rim=False),
    "retail": dict(style="flush", colorway="classic"),
    "ekasi": dict(style="relief", colorway="ekasi", back="surf"),
}
# Bitcoin Ekasi's own logo, used with their permission. When the file is here, the Ekasi edition
# carries it edge to edge on the back; without it the edition falls back to the surfer.
EKASI_LOGO = os.path.join(HERE, "logos", "bitcoin-ekasi", "bitcoin-ekasi-logo.svg")
if os.path.isfile(EKASI_LOGO):
    EDITIONS["ekasi"] = dict(style="relief", colorway="classic", logo=EKASI_LOGO, logo_mode="color", logo_bleed=True)


# ----------------------------------------------------------------------------
# Build
# ----------------------------------------------------------------------------
@dataclass
class Part:
    name: str
    colour: str          # colour name
    solid: Manifold


def extrude(geom, z0, z1):
    """Shapely geometry -> manifold solid between z0 and z1."""
    out = Manifold()
    for p in polys(geom):
        if p.area < 0.01:
            continue
        rings = [np.asarray(p.exterior.coords)[:-1]] + [np.asarray(i.coords)[:-1] for i in p.interiors]
        cs = CrossSection(rings, FillRule.EvenOdd)
        out = out + Manifold.extrude(cs, z1 - z0).translate([0, 0, z0])
    return out


class Tag:
    """One keychain: 2-D layout of both faces, then the coloured solids."""

    def __init__(self, spec: Spec):
        self.s = s = spec
        self.payload = qr_payload(s.address, s.payload_mode)
        self.matrix, self.qr = qr_matrix(self.payload, s.error)
        n = self.matrix.shape[0]
        m = s.module
        self.qr_half = n * m / 2
        self.notes = []

        # ---- outline ---------------------------------------------------------
        if s.shape == "round":
            self.field_r = self.qr_half * math.sqrt(2) + 1.2 * m
            self.R = self.field_r + s.rim
            body = disc(self.R)
            self.field = disc(self.field_r)
            top = self.R
        else:
            side = 2 * self.qr_half + 4 * m + 2 * s.rim      # 2-module quiet zone + rim
            self.R = side / 2
            body = rounded_square(side, 4.0)
            self.field = rounded_square(side - 2 * s.rim, max(0.5, 4.0 - s.rim))
            top = self.R
        self.width = 2 * self.R
        self.height = 2 * self.R
        hole = None
        if s.tab:
            # The loop is the part that breaks on thin tags, so it gets a thick wall, sits as
            # low on the tag as the rim allows, and flows into the body through wide fillets
            # (no sharp inside corner for a crack to start from).
            hole_r, collar = s.hole / 2, 1.6
            tab_r = hole_r + s.loop_wall
            cy = top + max(hole_r + 0.3, hole_r + collar - s.rim)
            body = body.union(disc(tab_r, 0, cy)).buffer(s.loop_fillet).buffer(-s.loop_fillet)
            hole = disc(hole_r, 0, cy)
            body = body.difference(hole)
            self.field = self.field.difference(disc(hole_r + collar, 0, cy))
            self.height = cy + tab_r + self.R
            self.loop = dict(wall=s.loop_wall, hole=s.hole, centre_y=cy)
        self.outline = body
        self.rim_region = body.difference(self.field) if s.rim > 0 else Polygon()

        # ---- front face (as you look at it) ------------------------------------
        # The QR side carries the code and the rim, nothing else.
        comp = s.dark_comp if s.dark_comp is not None else (0.0 if s.style == "flush" else -0.02)
        dark = qr_shape(self.matrix, m, shrink=-comp)
        self.front_dark = clean(dark)
        self.qr_dark = dark

        # ---- back face (as you look at it) -------------------------------------
        self.back_art = {"ink": Polygon(), "accent": Polygon()}
        self.back_text = Polygon()
        inner_r = (self.field_r if s.shape == "round" else self.R - s.rim) - 1.0   # clear air to the rim
        bottom = s.back_bottom or ""                       # the back is an image, not words
        icon_r = inner_r
        texts = []
        if s.shape == "round":
            cap = 3.2
            for txt, is_top in ((s.back_top, True), (bottom, False)):
                if txt:
                    # letters that hang below the baseline (g j p q y @) need room so they never
                    # touch the rim: the lower text sits further in by that much
                    drop = 0.26 if (not is_top and any(ch in "gjpqy@,;" for ch in txt)) else 0.0
                    span = math.radians(72 if is_top else 76)
                    g, c, used = arc_text(txt, cap, inner_r - cap / 2 - drop * cap, top=is_top, max_half_angle=span)
                    if c < cap - 0.01:
                        g, c, used = arc_text(txt, c, inner_r - c / 2 - drop * c, top=is_top, max_half_angle=span)
                    texts.append(g)
                    icon_r = min(icon_r, inner_r - c * (1 + drop) - 1.4)
                    if c < 2.4:
                        self.notes.append(f"back text '{txt}' is small ({c:.1f} mm caps) - shorten it")
            centre_box = (icon_r * 1.38, icon_r * 1.38)
            centre_y = 0.0
        else:
            w = 2 * inner_r - 1.0
            y_top, y_bot = inner_r - 0.4, -inner_r + 0.4
            if s.back_top:
                g, c, _ = fit_line(s.back_top, w, 3.2)
                texts.append(affinity.translate(g, 0, y_top - c / 2))
                y_top -= c + 1.4
            if bottom:
                bl = bottom
                g, c, _ = fit_line(bl, w, 3.0)
                if c < 2.6 and "@" in bl:                # two lines: name / @domain
                    a, b = bl.split("@", 1)
                    g2, c2, _ = fit_line("@" + b, w, 3.0)
                    g1, c1, _ = fit_line(a, w, 3.0)
                    texts.append(affinity.translate(g2, 0, y_bot + c2 * 0.26 + c2 / 2))
                    texts.append(affinity.translate(g1, 0, y_bot + c2 * 1.26 + 1.1 + c1 * 0.26 + c1 / 2))
                    y_bot += c2 * 1.26 + c1 * 1.26 + 2.4
                else:
                    texts.append(affinity.translate(g, 0, y_bot + c * 0.26 + c / 2))
                    y_bot += c * 1.26 + 1.4
            centre_box = (w, y_top - y_bot)
            centre_y = (y_top + y_bot) / 2
        if s.back_lines and not s.logo:
            lines = [l for l in s.back_lines if l]
            cap = min(4.4, (centre_box[1] - 1.2 * (len(lines) - 1)) / len(lines))
            fitted = [fit_line(l, centre_box[0] * (0.98 if s.shape != "round" else 0.92), cap) for l in lines]
            total = sum(f[1] for f in fitted) + 1.4 * (len(lines) - 1)
            y = centre_y + total / 2
            for g, c, _ in fitted:
                texts.append(affinity.translate(g, 0, y - c / 2))
                y -= c + 1.4
        elif s.logo or (s.back and s.back != "none"):
            if s.logo:
                col_ = s.colours()
                art, notes = load_art(s.logo, s.logo_mode,
                                      {"field": _hex(col_["field"]), "ink": _hex(col_["ink"]),
                                       "accent": _hex(col_["accent"])})
                self.notes.extend(notes)
            else:
                art = {"ink": Polygon(), "accent": icon(s.back)}
            whole = unary_union(list(art.values()))
            # Make the artwork as large as its own shape allows: grow it until it would come
            # within 0.8 mm of the text or 0.4 mm of the rim, trying a few heights when the
            # space above it is free.
            text_zone = unary_union(texts).buffer(0.8) if texts else Polygon()
            if s.shape == "round":
                room = disc(inner_r - 0.4 + 1.0 * (0 if texts else 0))
            else:
                room = rounded_square(2 * inner_r, 2.0)
            hull = whole.simplify(0.004)
            offsets = [centre_y] if (s.back_top or s.shape != "round") else \
                [centre_y + t * inner_r for t in (0.0, 0.04, 0.08, 0.12, 0.16, 0.2)]

            def fits(k, y0):
                g = affinity.translate(affinity.scale(hull, k, k, origin=(0, 0)), 0, y0)
                return room.contains(g) and not g.intersects(text_zone)

            best = (0.0, centre_y)
            for y0 in offsets:
                lo, hi = 0.0, 2.2 * inner_r
                for _ in range(18):
                    mid = (lo + hi) / 2
                    lo, hi = (mid, hi) if fits(mid, y0) else (lo, mid)
                if lo > best[0] * 1.01:
                    best = (lo, y0)
            k, centre_y = best[0] * 0.97, best[1]
            k *= s.logo_scale if s.logo else 1.0
            bleed = bool(s.logo and s.logo_bleed and s.shape == "round")
            if bleed:
                # A round badge: its circle becomes the tag's circle. The rim is dropped (the
                # badge has its own edge) and the loop takes the badge's outer colour.
                k, centre_y = 2 * self.R * s.logo_scale, 0.0
                s.back_rim = False
            for role in art:
                g = affinity.translate(affinity.scale(art[role], k, k, origin=(0, 0)), 0, centre_y)
                if g.is_empty:
                    continue
                # hair-thin details will not print: fatten them a little, twice at most, then say so
                for _ in range(2):
                    opened = g.buffer(-0.21).buffer(0.21)
                    if g.area == 0 or opened.area / g.area >= 0.97:
                        break
                    g = g.buffer(0.07)
                opened = g.buffer(-0.21).buffer(0.21)
                if g.area > 0 and opened.area / g.area < 0.9:
                    name = os.path.basename(s.logo) if s.logo else s.back
                    self.notes.append(f"'{name}' has detail finer than 0.4 mm that will soften or drop out - "
                                      f"use a simpler version of the artwork")
                self.back_art[role] = clean(g)
            if bleed:
                beyond = self.outline.difference(disc(self.R * s.logo_scale - 0.05))
                self.back_art["ink"] = clean(unary_union([self.back_art["ink"], beyond]).intersection(self.outline))
                self.back_art["accent"] = clean(self.back_art["accent"].intersection(self.outline))
            if not self.back_art["ink"].is_empty and not self.back_art["accent"].is_empty:
                self.back_art["accent"] = clean(self.back_art["accent"].difference(self.back_art["ink"]))
        # +0.05 mm all round: hairline strokes (the "@", thin joins) become printable lines
        self.back_text = clean(unary_union(texts).buffer(0.05)) if texts else Polygon()
        art_all = unary_union(list(self.back_art.values()))
        if not self.back_text.is_empty and not art_all.is_empty:
            self.back_text = clean(self.back_text.difference(art_all.buffer(0.6)))
        self.back_icon = art_all                              # kept for callers that want the outline

        self._build()

    # ------------------------------------------------------------------------
    BEVEL = (0.45, 0.25, 0.10)      # edge set-back of the three outermost layers on each face (mm)

    def _build(self):
        """Stack the tag layer by layer. Each 0.2 mm layer is a set of coloured regions; the
        outermost three layers on both faces step in to give a 45-degree bevelled edge."""
        s = self.s
        col = s.colours()
        ink, fld = col["ink"], col["field"]
        if s.invert:
            ink, fld = fld, ink
        light_over_dark = lambda c: c != col["body"] and c in LIGHT   # noqa: E731

        art = self.back_art
        art_all = unary_union(list(art.values()))
        back_ink = clean(unary_union([self.back_text] + ([self.rim_region] if s.back_rim else [])))
        back_regions = []
        if not art["accent"].is_empty:
            back_regions.append(("back-icon", col["accent"], art["accent"]))
        if not art["ink"].is_empty:
            back_regions.append(("back-logo", col["ink"], art["ink"]))
        if not back_ink.is_empty:
            back_regions.append(("back-text", col["ink"], clean(back_ink.difference(art_all))))
        if col["field"] != col["body"]:
            used = unary_union([art_all, back_ink])
            back_field = self.field if s.back_rim else self.outline
            back_regions.append(("back-field", col["field"], clean(back_field.difference(used))))
        has_back = any(c != col["body"] for _, c, _ in back_regions)
        d_back = (s.inlay + (2 * LAYER if light_over_dark(col["field"]) else 0)) if has_back else 0.0

        front_ink = clean(unary_union([self.front_dark, self.rim_region]))
        pocket = disc(13.0)
        plans = []      # (z0, z1, key, regions, mirrored, body_shape or None)
        if s.style == "flush":
            T = s.thickness
            d_f = s.inlay + (2 * LAYER if light_over_dark(fld) else 0)
            front_regions = [("front-qr", ink, front_ink),
                             ("front-field", fld, clean(self.field.difference(front_ink)))]
            plans.append((0, d_f, "front", front_regions, True, self.outline))      # QR on the build plate
            if s.nfc:
                z_n0, z_n1 = d_f + 0.6, d_f + 1.2
                if T - d_back - z_n1 < 0.6 - 1e-6:        # keep a 3-layer roof over the sticker
                    T = z_n1 + 0.6 + d_back
                    self.notes.append(f"thickness raised to {T:.1f} mm to fit the NFC pocket")
                plans += [(d_f, z_n0, "core", [], False, self.outline),
                          (z_n0, z_n1, "pocket", [], False, self.outline.difference(pocket)),
                          (z_n1, T - d_back, "core", [], False, self.outline)]
                self.nfc_pause_layer = int(round(z_n1 / LAYER)) + 1
            else:
                plans.append((d_f, T - d_back, "core", [], False, self.outline))
            if d_back:
                plans.append((T - d_back, T, "back", back_regions, False, self.outline))
            self.total_h, self.qr_on_bed = T, True
        else:                                               # relief: QR face-up, raised
            base = s.base
            d_fld = 2 * LAYER if fld != col["body"] else 0
            h_mod = max(s.relief, 0.6) if ink in LIGHT else s.relief   # light plastic needs 3 layers to cover
            if d_back:
                plans.append((0, d_back, "back", back_regions, True, self.outline))  # back on the build plate
            plans.append((d_back, base - d_fld, "core", [], False, self.outline))
            if d_fld:
                plans.append((base - d_fld, base, "field", [("front-field", fld, self.field)], False, self.outline))
            plans.append((base, base + h_mod, "raised",
                          [("front-qr", ink, self.front_dark), ("front-rim", ink, self.rim_region)], False, None))
            if not self.rim_region.is_empty and s.rim_extra > 0:
                plans.append((base + h_mod, base + h_mod + s.rim_extra, "rim",
                              [("front-rim", ink, self.rim_region)], False, None))
                self.total_h = base + h_mod + s.rim_extra
            else:
                self.total_h = base + h_mod
            self.qr_on_bed = False

        nl = int(round(self.total_h / LAYER))
        bev = self.BEVEL

        def plan_at(z):
            for p in plans:
                if p[0] - 1e-6 <= z < p[1] - 1e-6:
                    return p
            return plans[-1]

        # consecutive layers that are identical become one slab
        runs = []
        for k in range(nl):
            p = plan_at((k + 0.5) * LAYER)
            inset = max(bev[k] if k < len(bev) else 0.0, bev[nl - 1 - k] if nl - 1 - k < len(bev) else 0.0)
            key = (id(p), inset)
            if runs and runs[-1][0] == key:
                runs[-1][2] = (k + 1) * LAYER
            else:
                runs.append([key, k * LAYER, (k + 1) * LAYER, p, inset])

        parts = {}

        def add(name, colour, solid):
            if solid.is_empty():
                return
            key = (name, colour)
            parts[key] = parts[key] + solid if key in parts else solid

        clips = {}
        for _, z0, z1, p, inset in runs:
            if inset not in clips:
                clips[inset] = self.outline.buffer(-inset) if inset else self.outline
            clip = clips[inset]
            _, _, _, regions, mirrored, body_shape = p
            used = Polygon()
            for name, colour, geom in regions:
                g = clean((mirror_x(geom) if mirrored else geom).intersection(clip))
                if g.is_empty:
                    continue
                if body_shape is not None and colour == col["body"]:
                    continue                                 # same filament as the body: leave it in the body
                add(name, colour, extrude(g, z0, z1))
                used = used.union(g)
            if body_shape is not None:
                add("body", col["body"], extrude(clean(body_shape.intersection(clip).difference(used)), z0, z1))

        order = ["body", "front-field", "front-qr", "front-rim", "back-field", "back-text", "back-logo", "back-icon"]
        self.parts = [Part(n, c, parts[(n, c)]) for n in order for (pn, c) in list(parts) if pn == n]

        # filament slots: body first, then in order of appearance
        seen = []
        for want in (col["body"], col["field"], col["ink"], col["accent"]):
            if want not in seen and any(p.colour == want for p in self.parts):
                seen.append(want)
        self.filaments = seen
        if len(seen) > 4:
            self.notes.append("more than 4 colours - the AMS lite holds 4")

    # ------------------------------------------------------------------------
    def slot(self, colour):
        return self.filaments.index(colour) + 1

    def stats(self):
        vol = {}
        for p in self.parts:
            vol[p.colour] = vol.get(p.colour, 0) + p.solid.volume()
        grams = {c: v / 1000 * PLA_DENSITY for c, v in vol.items()}
        # which filaments appear in each layer -> lower bound on colour changes for a whole plate
        layers = []
        nl = int(round(self.total_h / LAYER))
        for i in range(nl):
            z = (i + 0.5) * LAYER
            present = set()
            for p in self.parts:
                bb = p.solid.bounding_box()
                if bb[2] - 1e-6 <= z <= bb[5] + 1e-6:
                    sl = p.solid.slice(z)
                    if sl.area() > 0.05:
                        present.add(p.colour)
            layers.append(present)
        swaps, cur = 0, None
        for i, S in enumerate(layers):
            if not S:
                continue
            nxt = layers[i + 1] if i + 1 < len(layers) else set()
            if cur in S:
                swaps += len(S) - 1
                rest = S - {cur}
            else:
                swaps += len(S) - (1 if cur is None else 0)
                rest = set(S)
            if len(S) > 1 or cur not in S:
                keep = (rest & nxt) or rest or S
                cur = sorted(keep)[0]
        return dict(grams=grams, total_g=sum(grams.values()), layers=nl, swaps=swaps,
                    multicolour_layers=sum(1 for S in layers if len(S) > 1))

    def describe(self):
        st = self.stats()
        s = self.s
        d = dict(
            address=s.address, payload=self.payload, qr_version=self.qr.version,
            qr_error=self.qr.error, modules=int(self.matrix.shape[0]), module_mm=s.module,
            size_mm=f"{self.width:.1f} x {self.height:.1f} x {self.total_h:.1f}",
            style=s.style, colorway=s.colorway,
            filaments={f"slot {i + 1}": c for i, c in enumerate(self.filaments)},
            grams={c: round(g, 2) for c, g in st["grams"].items()}, total_g=round(st["total_g"], 2),
            layers=st["layers"], colour_changes_per_plate=st["swaps"],
            qr_face="down (on the plate)" if self.qr_on_bed else "up",
            notes=self.notes,
        )
        if getattr(self, "nfc_pause_layer", None):
            d["nfc_pause_before_layer"] = self.nfc_pause_layer
        return d


# ----------------------------------------------------------------------------
# 3MF (Bambu Studio project flavour: one object per tag, one part per colour)
# ----------------------------------------------------------------------------
def _mesh_xml(solid):
    mesh = solid.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3]
    t = np.asarray(mesh.tri_verts)
    out = ["<mesh><vertices>"]
    out.extend(f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in v)
    out.append("</vertices><triangles>")
    out.extend(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in t)
    out.append("</triangles></mesh>")
    return "".join(out), len(t)


def _esc(s):
    return (s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;"))


def write_3mf(path, placed, filaments, title="Lightning keychains"):
    """placed: [(Tag, x, y)] in bed coordinates. filaments: ordered colour names (slot 1..n)."""
    slot = {c: i + 1 for i, c in enumerate(filaments)}
    objs, build, cfg = [], [], ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    oid = 0
    for n, (tag, x, y) in enumerate(placed, 1):
        comp_ids, part_cfg, faces = [], [], 0
        for p in tag.parts:
            oid += 1
            xml, nt = _mesh_xml(p.solid)
            faces += nt
            objs.append(f'<object id="{oid}" type="model">{xml}</object>')
            comp_ids.append(oid)
            part_cfg.append(
                f'    <part id="{oid}" subtype="normal_part">\n'
                f'      <metadata key="name" value="{_esc(p.name)} ({p.colour})"/>\n'
                f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                f'      <metadata key="extruder" value="{slot[p.colour]}"/>\n'
                f'    </part>')
        oid += 1
        comps = "".join(f'<component objectid="{c}" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>' for c in comp_ids)
        objs.append(f'<object id="{oid}" type="model"><components>{comps}</components></object>')
        build.append(f'<item objectid="{oid}" transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} 0" printable="1"/>')
        name = tag.s.name or tag.s.address
        cfg.append(f'  <object id="{oid}">\n    <metadata key="name" value="{_esc(name)}"/>\n'
                   f'    <metadata key="extruder" value="{slot[tag.parts[0].colour]}"/>\n'
                   + "".join(f'    <metadata key="{k}" value="{v}"/>\n' for k, v in PRINT_SETTINGS.items()) +
                   f''
                   f'    <metadata face_count="{faces}"/>\n' + "\n".join(part_cfg) + "\n  </object>")
    cfg.append("</config>")
    model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
        'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">\n'
        ' <metadata name="Application">BambuStudio-01.09.00.70</metadata>\n'
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        f' <metadata name="Title">{_esc(title)}</metadata>\n'
        ' <metadata name="Designer">lnkey</metadata>\n'
        ' <resources>\n' + "\n".join(objs) + "\n </resources>\n"
        ' <build>\n' + "\n".join(build) + "\n </build>\n</model>\n")
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
        ' <Default Extension="config" ContentType="text/xml"/>\n</Types>\n')
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", "\n".join(cfg))
    return path


def write_stls(prefix, tag):
    """One binary STL per colour (for other slicers)."""
    import struct
    out = []
    by = {}
    for p in tag.parts:
        by[p.colour] = by[p.colour] + p.solid if p.colour in by else p.solid
    for colour, solid in by.items():
        mesh = solid.to_mesh()
        v = np.asarray(mesh.vert_properties)[:, :3].astype(np.float32)
        t = np.asarray(mesh.tri_verts)
        tri = v[t]
        nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        ln = np.linalg.norm(nrm, axis=1, keepdims=True)
        nrm = np.where(ln > 0, nrm / np.maximum(ln, 1e-12), 0).astype(np.float32)
        path = f"{prefix}_{tag.slot(colour)}-{colour}.stl"
        with open(path, "wb") as f:
            f.write(b"lnkey".ljust(80, b" "))
            f.write(struct.pack("<I", len(t)))
            for i in range(len(t)):
                f.write(nrm[i].tobytes() + tri[i].tobytes() + b"\0\0")
        out.append(path)
    return out


def layout(tags, gap=2.5, margin=4.0, tower=(38.0, 38.0)):
    """Rows of tags on A1 plates, leaving the front-left corner free for the prime tower."""
    plates, cur, x, y, row_h = [], [], margin, margin, 0.0
    for t in tags:
        w, h = t.width, t.height
        if x + w > BED - margin:
            x, y, row_h = margin, y + row_h + gap, 0.0
        if y < margin + tower[1] and x < margin + tower[0]:
            x = margin + tower[0]
        if y + h > BED - margin:
            plates.append(cur)
            cur, x, y, row_h = [], margin + tower[0], margin, 0.0
        # tag origin is the disc centre; its bottom edge sits R below
        cur.append((t, x + w / 2, y + t.R))
        x += w + gap
        row_h = max(row_h, h)
    if cur:
        plates.append(cur)
    return plates


# ----------------------------------------------------------------------------
# Previews
# ----------------------------------------------------------------------------
def draw_face(ax, tag, face, cx=0.0, cy=0.0, shadow=True):
    """Flat picture of one face the way a person sees it. Built from the actual solids."""
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath
    top_view = (face == "front") != tag.qr_on_bed          # is this face the top of the print?
    eps = 0.05

    def patch(geom, colour, z, alpha=1.0, edge=None):
        for p in polys(geom):
            verts, codes = [], []
            for ring in [p.exterior] + list(p.interiors):
                c = np.asarray(ring.coords)
                verts.extend(c)
                codes.extend([MPath.MOVETO] + [MPath.LINETO] * (len(c) - 2) + [MPath.CLOSEPOLY])
            v = np.asarray(verts) + [cx, cy]
            ax.add_patch(PathPatch(MPath(v, codes), facecolor=colour, edgecolor=edge or "none",
                                   lw=0.4, alpha=alpha, zorder=z))

    if shadow:
        patch(affinity.translate(tag.outline, 0.7, -0.9), "#000000", 1, alpha=0.18)
    # the bevelled edge: the full outline, a shade off the edge colour, shows as a thin ring
    edge_part = next((p for p in tag.parts if p.name in ("front-rim", "front-qr", "back-text")), tag.parts[0])
    if face == "back" and not tag.s.back_rim:
        edge_part = tag.parts[0]
    rgb = [int(COLORS[edge_part.colour][i:i + 2], 16) for i in (1, 3, 5)]
    shade = "#%02x%02x%02x" % tuple(int(c * 0.72 + 128 * 0.28) for c in rgb)
    patch(tag.outline if top_view else mirror_x(tag.outline), shade, 1.5)
    for p in tag.parts:
        bb = p.solid.bounding_box()
        zs = [bb[5] - eps] if top_view else [bb[2] + eps]
        if top_view and p.name == "body":
            zs = [tag.s.base - eps if tag.s.style == "relief" else bb[5] - eps]
        for z in zs:
            cs = p.solid.slice(z)
            rings = cs.to_polygons()
            if not rings:
                continue
            geom = Polygon()
            for r in rings:                                  # even-odd assemble
                geom = geom.symmetric_difference(Polygon(np.asarray(r)).buffer(0))
            if not top_view:
                geom = mirror_x(geom)
            zorder = 2 + bb[5] if top_view else 2 + (10 - bb[2])
            patch(geom, COLORS[p.colour], zorder)
    edge = tag.outline if top_view else mirror_x(tag.outline)
    for p in polys(edge):
        for ring in [p.exterior] + list(p.interiors):
            c = np.asarray(ring.coords) + [cx, cy]
            ax.plot(c[:, 0], c[:, 1], color="#00000040", lw=0.5, zorder=40)


def preview(tag, path, dpi=200, title=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    W, H = tag.width + 8, tag.height + 8
    fig, axes = plt.subplots(1, 2, figsize=(2 * W / 25.4 * 1.6, H / 25.4 * 1.6 + 0.5), dpi=dpi)
    for ax, face in zip(axes, ("front", "back")):
        draw_face(ax, tag, face)
        ax.set_xlim(-W / 2, W / 2)
        ax.set_ylim(-tag.R - 4, tag.height - tag.R + 4)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(face, fontsize=9, color="#555")
    if title:
        fig.suptitle(title, fontsize=10)
    fig.patch.set_facecolor("#E9E6DF")
    fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return path


def qr_png(tag, path, scale=12):
    """Plain QR image of the exact payload - scan it off your screen before you print."""
    tag.qr.save(path, scale=scale, border=4)
    return path


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def spec_from(address, edition="retail", **over):
    base = dict(EDITIONS[edition])
    over = {k: v for k, v in over.items() if v is not None}
    if base.get("logo") and (over.get("back") or over.get("logo")):
        for k in ("logo", "logo_mode", "logo_bleed"):      # another back was asked for: drop the edition's logo
            base.pop(k, None)
    if over.get("logo") and "back_top" not in over:
        base["back_top"] = ""                              # a logo usually carries its own name
    base.update(over)
    return Spec(address=address, edition=edition, **base)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def make(spec, outdir, stl=False, png=True, quiet=False):
    os.makedirs(outdir, exist_ok=True)
    tag = Tag(spec)
    stem = os.path.join(outdir, f"{slug(spec.name or spec.address)}_{spec.edition}")
    write_3mf(stem + ".3mf", [(tag, BED / 2, BED / 2)], tag.filaments, title=spec.address)
    if stl:
        write_stls(stem, tag)
    if png:
        preview(tag, stem + "_preview.png")
        qr_png(tag, stem + "_qr-test.png")
    info = tag.describe()
    with open(stem + ".json", "w") as f:
        d = asdict(spec)
        if d.get("logo") and os.path.isabs(d["logo"]) and d["logo"].startswith(HERE + os.sep):
            d["logo"] = os.path.relpath(d["logo"], HERE)      # keep machine paths out of the record
        json.dump(dict(spec=d, build=info), f, indent=1, ensure_ascii=False)
    if not quiet:
        print(f"{stem}.3mf")
        for k in ("payload", "size_mm", "filaments", "total_g", "colour_changes_per_plate", "qr_face"):
            print(f"   {k}: {info[k]}")
        print(f"   qr: version {info['qr_version']} ({info['modules']}x{info['modules']}), "
              f"error correction {info['qr_error']}, {info['module_mm']} mm modules")
        if "nfc_pause_before_layer" in info:
            print(f"   NFC: add a pause before layer {info['nfc_pause_before_layer']} and drop the sticker in")
        for n in info["notes"]:
            print("   NOTE:", n)
    return tag, stem


def run_batch(csv_path, outdir, stl=False):
    """orders.csv -> one .3mf per order plus full plates grouped by filament set."""
    os.makedirs(outdir, exist_ok=True)
    tags = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            if not row.get("address") or row["address"].startswith("#"):
                continue
            over = {}
            for k in ("shape", "style", "colorway", "back", "name", "logo", "logo_mode",
                      "payload_mode"):
                if row.get(k):
                    over[k] = row[k]
            if row.get("logo_bleed", "").lower() in ("1", "y", "yes", "true"):
                over["logo_bleed"] = True
            if row.get("module"):
                over["module"] = float(row["module"])
            if row.get("nfc", "").lower() in ("1", "y", "yes", "true"):
                over["nfc"] = True
            spec = spec_from(row["address"], row.get("edition") or "retail", **over)
            tag, stem = make(spec, os.path.join(outdir, "single"), stl=stl, quiet=True)
            qty = int(row.get("qty") or 1)
            tags.extend([tag] * qty)
            print(f"{row['address']:36s} x{qty}  {spec.edition:7s} {tag.describe()['size_mm']}")
    # Tags that print the same way (same style, same height) and need no more than four
    # filaments between them share plates: colour changes are paid per plate, not per tag.
    groups = []
    for t in sorted(tags, key=lambda t: (t.s.style, round(t.total_h, 2), -len(t.filaments))):
        for g in groups:
            union = g["fil"] + [c for c in t.filaments if c not in g["fil"]]
            if g["key"] == (t.s.style, round(t.total_h, 2)) and len(union) <= 4:
                g["fil"], _ = union, g["tags"].append(t)
                break
        else:
            groups.append(dict(key=(t.s.style, round(t.total_h, 2)), fil=list(t.filaments), tags=[t]))
    for g in groups:
        for i, plate in enumerate(layout(g["tags"]), 1):
            name = f"plate_{g['key'][0]}_{'-'.join(g['fil'])}_{i}.3mf"
            write_3mf(os.path.join(outdir, name), plate, g["fil"], title=name)
            plate_preview(plate, g["fil"], os.path.join(outdir, name[:-4] + ".png"))
            grams = sum(t.stats()["total_g"] for t, _, _ in plate)
            print(f"-> {name}: {len(plate)} tags, {grams:.0f} g, "
                  f"filaments {', '.join(f'{i + 1}={c}' for i, c in enumerate(g['fil']))}, "
                  f"~{max(t.stats()['swaps'] for t, _, _ in plate)} colour changes for the whole plate")


def plate_preview(plate, filaments, path):
    """Top-down picture of a plate as it lies on the printer (the faces that print upward)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 6), dpi=130)
    ax.add_patch(plt.Rectangle((0, 0), BED, BED, facecolor="#3A3A3C", edgecolor="#111"))
    for tag, x, y in plate:
        draw_face(ax, tag, "back" if tag.qr_on_bed else "front", cx=x, cy=y, shadow=False)
    ax.set_xlim(-4, BED + 4)
    ax.set_ylim(-4, BED + 4)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"{len(plate)} tags  |  " + "  ".join(f"{i + 1}:{c}" for i, c in enumerate(filaments)), fontsize=9)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("address", nargs="?", help="Lightning address, e.g. jasonbohio@blink.sv")
    ap.add_argument("-o", "--out", default="out")
    ap.add_argument("--edition", choices=list(EDITIONS), default="retail")
    ap.add_argument("--shape", choices=["round", "square"])
    ap.add_argument("--style", choices=["flush", "relief"])
    ap.add_argument("--colorway", choices=list(COLORWAYS))
    ap.add_argument("--payload", dest="payload_mode", choices=["uri", "plain", "lnurl", "raw"])
    ap.add_argument("--module", type=float, help="QR module size in mm (default 1.0)")
    ap.add_argument("--error", choices=list("lmqh"), help="force QR error correction")
    ap.add_argument("--invert", action="store_true", default=None, help="light QR on a dark field")
    ap.add_argument("--back", help="icon alias, icon file name, path to an .svg, or 'none'")
    ap.add_argument("--logo", help="a logo file for the back (.svg, .png, .jpg) instead of an icon")
    ap.add_argument("--logo-mode", dest="logo_mode", choices=["mono", "color"],
                    help="mono: logo in one dark colour (default) | color: map its colours to the filaments")
    ap.add_argument("--logo-scale", dest="logo_scale", type=float, help="resize the logo within its space")
    ap.add_argument("--logo-bleed", dest="logo_bleed", action="store_true", default=None,
                    help="for a round badge logo: run it to the tag's edge, so the back is the badge")
    ap.add_argument("--no-back-rim", dest="back_rim", action="store_false", default=None)
    ap.add_argument("--nfc", action="store_true", default=None, help="26 mm pocket for an NFC sticker")
    ap.add_argument("--thickness", type=float)
    ap.add_argument("--name", help="file / object name (default: the address)")
    ap.add_argument("--stl", action="store_true", help="also write one STL per colour")
    ap.add_argument("--batch", metavar="orders.csv", help="build every row of a CSV and fill plates")
    ap.add_argument("--list-icons", nargs="?", const="", metavar="WORD")
    ap.add_argument("--list-colorways", action="store_true")
    a = ap.parse_args(argv)

    if a.list_icons is not None:
        hits = search_icons(a.list_icons)
        print("\n".join(hits[:400]))
        print(f"\n{len(hits)} matches" + (" (showing 400)" if len(hits) > 400 else ""))
        return
    if a.list_colorways:
        for k, v in COLORWAYS.items():
            print(f"{k:9s} body={v[0]:7s} field={v[1]:7s} ink={v[2]:6s} accent={v[3]}")
        return
    if a.batch:
        return run_batch(a.batch, a.out, stl=a.stl)
    if not a.address:
        ap.error("give a Lightning address, or --batch orders.csv")
    over = {k: getattr(a, k) for k in ("shape", "style", "colorway", "payload_mode", "module", "error",
                                        "invert", "back", "logo", "logo_mode", "logo_scale", "logo_bleed",
                                        "back_rim", "nfc", "thickness", "name")}
    make(spec_from(a.address, a.edition, **over), a.out, stl=a.stl)


if __name__ == "__main__":
    main()
