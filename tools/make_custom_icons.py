#!/usr/bin/env python3
"""Draws the two icons this kit adds on top of Material Design Icons (trombone, food-truck)
and saves them as plain SVG files in ../icons. Original artwork, free to use."""
import math, os
import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely import affinity

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "icons")


def tube(pts, w=1.0):
    return LineString(pts).buffer(w / 2, cap_style="round", join_style="round")


def arc(cx, cy, r, a0, a1, n=24):
    return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in np.linspace(a0, a1, n)]


def trombone():
    w = 1.05
    parts = []
    # slide: two long tubes with a U-bend at the far (left) end
    parts.append(tube([(17.2, 9.2)] + [(3.2, 9.2)] + arc(3.2, 7.6, 1.6, 90, 270) + [(3.2, 6.0), (19.6, 6.0)], w))
    # mouthpiece
    parts.append(Polygon([(19.4, 5.45), (21.4, 5.05), (22.3, 4.7), (22.3, 7.3), (21.4, 6.95), (19.4, 6.55)]))
    # back bow, then the bell tube running forward
    parts.append(tube([(17.0, 9.2), (19.4, 9.2)] + arc(19.4, 11.35, 2.15, -90, 90) + [(19.4, 13.5), (11.5, 13.5)], w))
    # bell flare
    xs = np.linspace(12.0, 4.2, 30)
    half = [0.52 + 3.1 * ((12.0 - x) / 7.8) ** 2.6 for x in xs]
    parts.append(Polygon([(x, 13.5 + h) for x, h in zip(xs, half)] + [(x, 13.5 - h) for x, h in zip(xs[::-1], half[::-1])]))
    # braces
    parts.append(tube([(8.2, 6.0), (8.2, 9.2)], 0.8))
    parts.append(tube([(15.2, 9.2), (15.2, 13.5)], 0.8))
    parts.append(tube([(17.6, 6.0), (17.6, 9.2)], 0.8))
    return unary_union(parts)


def food_truck():
    body = box(1.5, 7.0, 15.5, 17.5).buffer(0.6).buffer(-0.0)
    cab = Polygon([(15.5, 7.0), (22.6, 7.0), (22.6, 11.6), (20.2, 15.0), (15.5, 15.0)]).buffer(0.5, join_style="round")
    shape = unary_union([body, cab])
    awning = Polygon([(2.2, 16.2), (14.8, 16.2), (15.8, 14.3), (1.2, 14.3)])
    window = box(3.4, 10.6, 13.6, 14.3)
    cab_win = Polygon([(17.0, 11.6), (21.2, 11.6), (19.6, 14.0), (17.0, 14.0)])
    shape = shape.difference(window).difference(cab_win).union(awning)
    # counter shelf under the serving window
    shape = shape.union(box(2.6, 9.7, 14.4, 10.6))
    for cx in (6.0, 18.6):
        shape = shape.difference(Point(cx, 6.6).buffer(2.75))
        shape = shape.union(Point(cx, 6.6).buffer(2.1).difference(Point(cx, 6.6).buffer(0.8)))
    return shape


def orange_pill():
    cap = LineString([(12, 5.2), (12, 18.8)]).buffer(4.2, cap_style="round")
    gap = box(6, 11.45, 18, 12.55)
    shine = LineString([(10.2, 14.6), (10.2, 17.4)]).buffer(0.75, cap_style="round")
    return affinity.rotate(cap.difference(gap).difference(shine), -42, origin=(12, 12))


def sats():
    bars = [box(5.2, y - 1.25, 18.8, y + 1.25) for y in (7.6, 12.0, 16.4)]
    ticks = [box(10.75, 2.2, 13.25, 4.9), box(10.75, 19.1, 13.25, 21.8)]
    return unary_union(bars + ticks)


BOLT = Polygon([(13.6, 4.6), (8.2, 12.9), (11.6, 12.9), (10.4, 19.4), (15.8, 11.1), (12.4, 11.1)])


def zap_coin():
    coin = Point(12, 12).buffer(10.4, 64)
    ring = Point(12, 12).buffer(8.6, 64).difference(Point(12, 12).buffer(7.5, 64))
    return coin.difference(ring).difference(BOLT.buffer(0.25, join_style="mitre"))


def tip_jar():
    body = box(6.0, 2.6, 18.0, 15.4).buffer(1.4, join_style="round")
    neck = box(7.6, 15.6, 16.4, 18.4)
    lid = box(6.4, 18.4, 17.6, 21.0).buffer(0.5)
    jar = unary_union([body, neck, lid])
    slot = box(9.4, 19.3, 14.6, 20.3)
    bolt = affinity.translate(affinity.scale(BOLT, 0.86, 0.86, origin=(12, 12)), 0, -2.9)
    return jar.difference(slot).difference(bolt.buffer(0.2, join_style="mitre"))


def heater():
    case = box(3.2, 4.0, 20.8, 15.6).buffer(1.0, join_style="round")
    fan = Point(9.0, 9.8).buffer(4.0, 48)
    hub = Point(9.0, 9.8).buffer(1.25, 32)
    blades = unary_union([affinity.rotate(box(8.45, 9.8, 9.55, 13.4), a, origin=(9.0, 9.8)) for a in (0, 72, 144, 216, 288)])
    vents = unary_union([box(15.2, y, 19.2, y + 1.0) for y in (6.2, 8.4, 10.6, 12.8)])
    feet = unary_union([box(5.0, 2.4, 7.4, 3.6), box(16.6, 2.4, 19.0, 3.6)])
    waves = []
    for x in (7.2, 12.0, 16.8):
        pts = [(x + 0.9 * math.sin((y - 17.4) * 1.9), y) for y in np.linspace(17.4, 21.6, 14)]
        waves.append(LineString(pts).buffer(0.62, cap_style="round"))
    return unary_union([case.difference(fan).difference(vents), hub, blades.intersection(fan), feet] + waves)


def bitcoin_coin():
    """The Bitcoin mark (public domain): a disc with the tilted B knocked out, counters and all."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    import lnkey
    # the Material Design file itself: "bitcoin" as a name is an alias for this coin
    b = lnkey.load_svg(os.path.join(lnkey.ICON_DIR, "bitcoin.svg"))    # unit-size disc, B cut out
    return affinity.translate(affinity.scale(b, 22, 22, origin=(0, 0)), 12, 12)


def to_svg(geom, name):
    geom = affinity.scale(geom, 1, -1, origin=(12, 12))        # SVG y runs down
    d = []
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    for p in polys:
        for ring, ccw in [(p.exterior, True)] + [(i, False) for i in p.interiors]:
            c = list(ring.coords)[:-1]
            area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(c, c[1:] + c[:1]))
            if (area > 0) != ccw:
                c = c[::-1]
            d.append("M" + "L".join(f"{x:.3f},{y:.3f}" for x, y in c) + "Z")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" id="lnkey-{name}" viewBox="0 0 24 24">'
           f'<path d="{"".join(d)}" /></svg>')
    with open(os.path.join(OUT, name + ".svg"), "w") as f:
        f.write(svg)


if __name__ == "__main__":
    to_svg(trombone(), "trombone")
    to_svg(food_truck(), "food-truck")
    for name, fn in (("orange-pill", orange_pill), ("sats", sats), ("zap-coin", zap_coin), ("tip-jar", tip_jar),
                     ("home-miner", heater), ("bitcoin-coin", bitcoin_coin)):
        to_svg(fn(), name)
    print("wrote trombone, food-truck, orange-pill, sats, zap-coin, tip-jar, home-miner")
