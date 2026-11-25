#!/usr/bin/env python3
"""
make_web_images.py - the website's pictures, from the same icon files the generator uses.

    python tools/make_web_images.py            # writes web/images.json
    python tools/make_web_images.py --badge logos/bitcoin-ekasi/bitcoin-ekasi-logo.svg \
        --id bitcoin-ekasi --label "Bitcoin Ekasi" --out web/ekasi.json

A picture is a list of closed rings in unit size (larger side = 1, centred, y up); the site fills
them by the even-odd rule. A badge is a round, multi-colour logo that takes over the whole back of
the tag: its dark colour becomes the face, and it is stored as three sets of rings -
`cut` (where the face colour is NOT), `light` and `accent`.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import lnkey  # noqa: E402
from shapely.geometry import Point  # noqa: E402

PICTURES = [  # (icon file, label on the site)
    ("bitcoin-coin", "Bitcoin"), ("lightning-bolt", "Bolt"), ("sats", "Sats"), ("orange-pill", "Orange pill"),
    ("zap-coin", "Zap"), ("tip-jar", "Tip jar"), ("home-miner", "Home miner"), ("surfing", "Surf"),
    ("coffee", "Coffee"), ("glass-cocktail", "Bar"), ("content-cut", "Barber"), ("trombone", "Trombone"),
    ("guitar-acoustic", "Guitar"), ("music", "Music"), ("microphone-variant", "Mic"), ("paw", "Pets"),
    ("egg", "Eggs"), ("food-truck", "Food truck"), ("wrench", "Repair"), ("camera", "Photo"),
    ("heart", "Heart"), ("star", "Star"), ("pizza", "Pizza"), ("bicycle", "Bike"),
]


def rings_of(geom, digits=4, apart=0.0):
    """Rings of a shape. Points closer than `apart` to the one before are dropped: the site nudges
    every vertex by a micron before triangulating, so vertices must not sit that close together."""
    out = []
    for p in (geom.geoms if hasattr(geom, "geoms") else [geom]):
        if p.is_empty or p.geom_type != "Polygon":
            continue
        for r in [p.exterior] + list(p.interiors):
            pts = []
            for x, y in list(r.coords)[:-1]:
                if pts and abs(x - pts[-1][0]) + abs(y - pts[-1][1]) < apart:
                    continue
                pts.append([round(x, digits), round(y, digits)])
            while len(pts) > 3 and abs(pts[0][0] - pts[-1][0]) + abs(pts[0][1] - pts[-1][1]) < apart:
                pts.pop()
            if len(pts) >= 3:
                out.append(pts)
    return out


def pictures(out):
    data = []
    for name, label in PICTURES:
        g = lnkey.load_svg(os.path.join(lnkey.ICON_DIR, name + ".svg")).simplify(0.0025)
        data.append({"id": name, "label": label, "rings": rings_of(g)})
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"wrote {out}: {len(data)} pictures, {os.path.getsize(out) // 1024} KB")


def badge(path, ident, label, out):
    art, notes = lnkey.load_art(path, "color")
    tol, gap = 0.0011, 0.00012                      # about 0.05 mm and 0.006 mm on a 47 mm tag
    ink = art["ink"].simplify(tol).buffer(0)
    accent = art["accent"].simplify(tol).buffer(0).difference(ink)
    face = Point(0, 0).buffer(0.5, 128)
    light = face.difference(ink).difference(accent)
    light = light.intersection(Point(0, 0).buffer(0.48, 128))      # the badge's own edge stays dark
    mitre = dict(join_style=2, mitre_limit=2.0)      # square corners: no clusters of arc points
    cut = light.union(accent).buffer(gap, **mitre)   # the dark face stops a hair short of both
    accent = accent.buffer(-gap, **mitre)            # ... and the accent a hair short of the light
    light = light.buffer(-gap / 2, **mitre)          # no two light shapes meet at a single point
    apart = 0.0003                                   # 0.014 mm on a 47 mm tag
    data = {"id": ident, "label": label, "badge": True, "cut": rings_of(cut, 5, apart),
            "light": rings_of(light, 5, apart), "accent": rings_of(accent, 5, apart)}
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    n = sum(len(r) for k in ("cut", "light", "accent") for r in data[k])
    print(f"wrote {out}: {n} points, {os.path.getsize(out) // 1024} KB", *notes)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--badge", help="a round multi-colour logo (.svg) to store as a badge")
    ap.add_argument("--id", default="badge")
    ap.add_argument("--label", default="Badge")
    ap.add_argument("--out")
    a = ap.parse_args()
    web = os.path.join(HERE, "..", "web")
    if a.badge:
        badge(a.badge, a.id, a.label, a.out or os.path.join(web, a.id + ".json"))
    else:
        pictures(a.out or os.path.join(web, "images.json"))
