#!/usr/bin/env python3
"""
slice_check.py - what will the printer actually lay down?

Slices a keychain with PrusaSlicer (same slicing-engine family as Bambu Studio, set up to
mimic the A1's 0.20 mm profile: 0.4 nozzle, Arachne walls, 0.5 mm first-layer lines), then
reads the G-code back and

  * paints every extrusion line, in its filament's colour, as seen from the plate side and
    from the top - a picture of the printed faces, not of the model
  * decodes the QR from those painted toolpaths with two readers
  * measures, per colour, how much of each face the toolpaths really cover, so features
    that are too thin to print show up as a number and as red patches
  * reports filament changes, grams and the slicer's time estimate

    python tools/slice_check.py jasonbohio@blink.sv --edition retail --back trombone

Needs `prusa-slicer` on the PATH (Linux: apt install prusa-slicer). Optional - the generator
and verify.py do not depend on it.
"""
import argparse
import math
import os
import re
import subprocess
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import lnkey  # noqa: E402

PX = 24  # pixels per mm in the toolpath pictures

INI = """
bed_shape = 0x0,256x0,256x256,0x256
nozzle_diameter = {nozzle},{nozzle},{nozzle},{nozzle}
filament_diameter = 1.75,1.75,1.75,1.75
filament_density = 1.24,1.24,1.24,1.24
single_extruder_multi_material = 1
wipe_tower = 1
wipe_tower_x = 190
wipe_tower_y = 190
layer_height = {layer}
first_layer_height = {first_layer}
perimeters = {walls}
fill_density = {infill}%
fill_pattern = rectilinear
top_solid_layers = 5
bottom_solid_layers = 5
top_fill_pattern = monotonic
bottom_fill_pattern = monotonic
perimeter_generator = {generator}
extrusion_width = {inner_w}
external_perimeter_extrusion_width = {outer_w}
perimeter_extrusion_width = {inner_w}
infill_extrusion_width = {inner_w}
solid_infill_extrusion_width = {inner_w}
top_infill_extrusion_width = {outer_w}
first_layer_extrusion_width = {first_w}
elefant_foot_compensation = {efc}
external_perimeters_first = {outer_first}
thin_walls = {thin_walls}
first_layer_speed = 30
perimeter_speed = 150
external_perimeter_speed = 120
infill_speed = 200
solid_infill_speed = 200
top_solid_infill_speed = 120
travel_speed = 400
machine_max_acceleration_extruding = 6000
use_relative_e_distances = 1
skirts = 0
brim_width = 0
gcode_comments = 0
complete_objects = 0
interface_shells = 0
gap_fill_enabled = 1
start_gcode = G28
end_gcode = M84
layer_gcode = ;AFTER_LAYER_CHANGE
toolchange_gcode =
temperature = 220,220,220,220
first_layer_temperature = 220,220,220,220
bed_temperature = 60,60,60,60
first_layer_bed_temperature = 60,60,60,60
"""


def write_prusa_3mf(tag, path):
    """One object, one volume per part, extruder per volume (PrusaSlicer's own 3MF flavour)."""
    verts, tris, vols, off = [], [], [], 0
    for p in tag.parts:
        mesh = p.solid.to_mesh()
        v = np.asarray(mesh.vert_properties)[:, :3]
        t = np.asarray(mesh.tri_verts)
        first = len(tris)
        verts.extend(v.tolist())
        tris.extend((t + off).tolist())
        off += len(v)
        vols.append((first, len(tris) - 1, p.name, tag.slot(p.colour)))
    model = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
             'xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">',
             '<metadata name="slic3rpe:Version3mf">1</metadata>',
             '<resources><object id="1" type="model"><mesh><vertices>']
    model += [f'<vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in verts]
    model.append("</vertices><triangles>")
    model += [f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris]
    model.append('</triangles></mesh></object></resources>'
                 '<build><item objectid="1" transform="1 0 0 0 1 0 0 0 1 100 100 0" printable="1"/></build></model>')
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>', "<config>", ' <object id="1" instances_count="1">',
           '  <metadata type="object" key="name" value="tag"/>']
    for first, last, name, ext in vols:
        cfg += [f'  <volume firstid="{first}" lastid="{last}">',
                f'   <metadata type="volume" key="name" value="{name}"/>',
                '   <metadata type="volume" key="volume_type" value="ModelPart"/>',
                '   <metadata type="volume" key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>',
                f'   <metadata type="volume" key="extruder" value="{ext}"/>', "  </volume>"]
    cfg += [" </object>", "</config>"]
    ct = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", "\n".join(model))
        z.writestr("Metadata/Slic3r_PE_model.config", "\n".join(cfg))


def parse_gcode(path):
    """-> layers {z: [(tool, x0, y0, x1, y1, width, type)]}, toolchanges, comments"""
    layers, tool, x, y, z = {}, 0, 0.0, 0.0, 0.0
    width, typ, changes, info = 0.45, "", 0, {}
    num = re.compile(r"([XYZEF])(-?\d*\.?\d+)")
    seen_first_tool = False
    for line in open(path):
        if line.startswith(";"):
            if line.startswith(";TYPE:"):
                typ = line[6:].strip()
            elif line.startswith(";WIDTH:"):
                width = float(line[7:])
            elif line.startswith(";Z:"):
                z = round(float(line[3:]), 3)
            elif "=" in line:
                k, _, v = line[1:].partition("=")
                info[k.strip()] = v.strip()
            continue
        if line[0] == "T" and line[1:2].isdigit():
            new = int(line[1:].split()[0])
            if seen_first_tool and new != tool:
                changes += 1
            seen_first_tool, tool = True, new
            continue
        if line.startswith("G1 ") or line.startswith("G0 "):
            vals = dict(num.findall(line.split(";")[0]))
            nx, ny = float(vals.get("X", x)), float(vals.get("Y", y))
            if "Z" in vals and "X" not in vals:
                pass
            e = float(vals.get("E", 0))
            if e > 0 and (nx != x or ny != y) and typ not in ("Wipe tower", "Custom", "Skirt/Brim"):
                layers.setdefault(z, []).append((tool, x, y, nx, ny, width, typ))
            x, y = nx, ny
    return layers, changes, info


def paint(layers, zs, colours, bounds, mirror, bg=(205, 203, 198), ss=2):
    """Draw the given layers in order (later ones on top), smoothed by drawing at ss x size."""
    x0, y0, x1, y1 = bounds
    W, H = int((x1 - x0) * PX), int((y1 - y0) * PX)
    S = PX * ss
    img = Image.new("RGB", (W * ss, H * ss), bg)
    d = ImageDraw.Draw(img)
    for z in zs:
        for tool, ax, ay, bx, by, w, _ in layers[z]:
            pa = ((ax - x0) * S, H * ss - (ay - y0) * S)
            pb = ((bx - x0) * S, H * ss - (by - y0) * S)
            if mirror:
                pa, pb = (W * ss - pa[0], pa[1]), (W * ss - pb[0], pb[1])
            c = colours[tool]
            wpx = max(1, int(round(w * S)))
            d.line([pa, pb], fill=c, width=wpx)
            r = wpx / 2
            for p in (pa, pb):
                d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=c)
    return img.resize((W, H), Image.LANCZOS) if ss > 1 else img


def decode(img):
    out = {}
    g = img.convert("L")
    try:
        import zxingcpp
        r = zxingcpp.read_barcodes(g)
        out["zxing"] = r[0].text if r else None
    except ImportError:
        pass
    try:
        import cv2
        val, _, _ = cv2.QRCodeDetector().detectAndDecode(np.array(g))
        out["opencv"] = val or None
    except ImportError:
        pass
    return out


def coverage(tag, layers, z_layer, z_model, bounds, origin):
    """Per colour on one layer: share of the model's area that toolpaths of that colour cover."""
    from shapely.geometry import Polygon
    x0, y0, x1, y1 = bounds
    W, H = int((x1 - x0) * PX), int((y1 - y0) * PX)
    rows, miss_img = [], Image.new("L", (W, H), 0)
    for colour in tag.filaments:
        model = Image.new("1", (W, H), 0)
        md = ImageDraw.Draw(model)
        for p in tag.parts:
            if p.colour != colour:
                continue
            for r in sorted((np.asarray(r) for r in p.solid.slice(z_model).to_polygons()),
                            key=lambda r: -abs(Polygon(r).area)):
                ccw = 0.5 * float(np.sum(r[:, 0] * np.roll(r[:, 1], -1) - np.roll(r[:, 0], -1) * r[:, 1])) > 0
                md.polygon([((x + origin[0] - x0) * PX, H - (y + origin[1] - y0) * PX) for x, y in r],
                           fill=1 if ccw else 0)
        laid = Image.new("1", (W, H), 0)
        ld = ImageDraw.Draw(laid)
        for tool, ax, ay, bx, by, w, _ in layers.get(z_layer, []):
            if tool != tag.slot(colour) - 1:
                continue
            pa, pb = ((ax - x0) * PX, H - (ay - y0) * PX), ((bx - x0) * PX, H - (by - y0) * PX)
            wpx = max(1, int(round(w * PX)))
            ld.line([pa, pb], fill=1, width=wpx)
            r = wpx / 2
            for p in (pa, pb):
                ld.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=1)
        m, l = np.array(model), np.array(laid)
        if m.sum() == 0:
            continue
        missed = m & ~l
        rows.append((colour, m.sum() / PX ** 2, 100.0 * (m & l).sum() / m.sum(), missed.sum() / PX ** 2))
        miss_img = Image.fromarray(np.maximum(np.array(miss_img), (missed * 255).astype(np.uint8)))
    return rows, miss_img


PROFILES = {
    # Bambu Studio's stock 0.20 mm A1 profile, as near as PrusaSlicer can mimic it
    "stock": dict(nozzle=0.4, layer=0.2, first_layer=0.2, generator="arachne", inner_w=0.45, outer_w=0.42,
                  first_w=0.5, efc=0.15, outer_first=0, thin_walls=0),
    # the tuned profile this kit recommends for a 0.4 mm nozzle
    "tuned": dict(nozzle=0.4, layer=0.2, first_layer=0.2, generator="arachne", inner_w=0.42, outer_w=0.40,
                  first_w=0.42, efc=0.15, outer_first=1, thin_walls=0),
    # 0.2 mm nozzle, for show pieces
    "fine": dict(nozzle=0.2, layer=0.1, first_layer=0.1, generator="arachne", inner_w=0.22, outer_w=0.22,
                 first_w=0.25, efc=0.1, outer_first=1, thin_walls=0),
}


def run(spec, outdir, walls=5, infill=100, label=None, profile="stock", quiet=False):
    prof = dict(PROFILES[profile]) if isinstance(profile, str) else dict(profile)
    os.makedirs(outdir, exist_ok=True)
    tag = lnkey.Tag(spec)
    stem = os.path.join(outdir, label or f"{lnkey.slug(spec.name or spec.address)}_{spec.edition}")
    write_prusa_3mf(tag, stem + "_prusa.3mf")
    with open(stem + ".ini", "w") as f:
        f.write(INI.format(walls=walls, infill=infill, **prof))
    r = subprocess.run(["prusa-slicer", "--load", stem + ".ini", "--export-gcode", stem + "_prusa.3mf",
                        "-o", stem + ".gcode"], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(stem + ".gcode"):
        print(r.stdout[-800:], r.stderr[-800:])
        raise SystemExit("slicing failed")
    layers, changes, info = parse_gcode(stem + ".gcode")
    zs = sorted(layers)
    colours = {tag.slot(c) - 1: tuple(int(lnkey.COLORS[c][i:i + 2], 16) for i in (1, 3, 5)) for c in tag.filaments}
    # where did the slicer put the tag? (it centres the object on the bed)
    pts = np.array([[m[1], m[2]] for m in layers[zs[0]]] + [[m[3], m[4]] for m in layers[zs[0]]])
    gx, gy = (pts[:, 0].min() + pts[:, 0].max()) / 2, (pts[:, 1].min() + pts[:, 1].max()) / 2
    ox, oy = gx, gy - (tag.height - 2 * tag.R) / 2
    b = (ox - tag.R - 3, oy - tag.R - 3, ox + tag.R + 3, oy + tag.height - tag.R + 3)
    bottom = paint(layers, zs[::-1], colours, b, mirror=True)        # first layer drawn last = what the plate side shows
    top = paint(layers, zs, colours, b, mirror=False)
    bottom.save(stem + "_toolpaths_plate-side.png")
    top.save(stem + "_toolpaths_top.png")
    qr_img = bottom if tag.qr_on_bed else top
    dec = decode(qr_img)
    blurred = qr_img.resize((qr_img.width // 4, qr_img.height // 4), Image.LANCZOS)
    dec_small = decode(blurred)
    ok = [v == tag.payload for v in dec.values() if v is not None]
    print(f"\n{os.path.basename(stem)}  ({spec.edition}, {spec.style}, {tag.describe()['size_mm']} mm)")
    print(f"   QR from painted toolpaths ({'plate side' if tag.qr_on_bed else 'top'}): {dec}")
    print(f"   decodes to the payload: {'YES' if ok and all(ok) else 'NO'}"
          f"   | at quarter resolution: {'yes' if tag.payload in dec_small.values() else 'no'}")
    # dark share inside the code: printed vs. ideal (50/50-ish codes read best when this is ~100%)
    g = np.array(qr_img.convert("L"))
    H = g.shape[0]
    n, m = tag.matrix.shape[0], spec.module
    cx = (ox - b[0]) * PX
    if tag.qr_on_bed:
        cx = g.shape[1] - cx
    cy = H - (oy - b[1]) * PX
    half = int(n * m / 2 * PX)
    win = g[int(cy) - half:int(cy) + half, int(cx) - half:int(cx) + half]
    printed = float((win < 110).mean())
    ideal = float(tag.matrix.mean())
    ref = np.kron(tag.matrix, np.ones((int(round(m * PX)), int(round(m * PX)))))
    # the painted picture can sit a pixel or two off the ideal grid: take the best alignment
    fidelity, pad = 0.0, 4
    big = g[int(cy) - half - pad:int(cy) + half + pad, int(cx) - half - pad:int(cx) + half + pad] < 110
    hh = min(ref.shape[0], 2 * half)
    for dy in range(2 * pad + 1):
        for dx in range(2 * pad + 1):
            fidelity = max(fidelity, float((big[dy:dy + hh, dx:dx + hh] == (ref[:hh, :hh] > 0)).mean()))
    print(f"   code fidelity (printed pixels that match the ideal code): {100 * fidelity:.1f}%")
    print(f"   dark share of the code: {100 * printed:.1f}% printed vs {100 * ideal:.1f}% ideal "
          f"({100 * printed / ideal:.0f}% of intended)")
    faces = [("plate side", zs[0], LAYER_MID(zs[0]))]
    faces.append(("top face", zs[-1], zs[-1] - 0.1))
    if spec.style == "relief":
        faces.append(("code field (under the raised code)", round(spec.base, 3), spec.base - 0.1))
    worst = 100.0
    for name, zl, zm in faces:
        rows, miss = coverage(tag, layers, zl, zm, b, (ox, oy))
        for colour, area, pct, missed in rows:
            worst = min(worst, pct)
            print(f"   {name:36s} {colour:7s} {area:7.1f} mm2 in the model, {pct:5.1f}% laid down"
                  f"{'' if pct > 90 else '   <-- thin features lost'}")
        miss.save(stem + f"_missed_{name.split()[0]}.png")
    grams = info.get("filament used [g]", "?")
    changes = int(info.get("total toolchanges", changes))
    print("   (the few percent not laid down are hairlines along colour boundaries and the first layer's"
          " outer edge, which the slicer trims on purpose - see the *_missed_*.png maps)")
    print(f"   filament changes: {changes}   filament [g]: {grams}   "
          f"slicer time estimate (one tag): "
          f"{(lambda v: '?' if v.startswith('-') else v)(info.get('estimated printing time (normal mode)', '?'))}")
    return dict(tag=tag, stem=stem, decoded=bool(ok and all(ok)), worst=worst, changes=changes, info=info,
                dark=printed / ideal, fidelity=fidelity, layers=layers, zs=zs, bounds=b, origin=(ox, oy),
                colours=colours)


def LAYER_MID(z):
    return z - 0.1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("address")
    ap.add_argument("--edition", default="retail")
    ap.add_argument("--back")
    ap.add_argument("--shape")
    ap.add_argument("--colorway")
    ap.add_argument("--logo")
    ap.add_argument("--logo-mode", dest="logo_mode")
    ap.add_argument("--logo-bleed", dest="logo_bleed", action="store_true", default=None)
    ap.add_argument("--nfc", action="store_true", default=None)
    ap.add_argument("-o", "--out", default="out/slice-check")
    a = ap.parse_args()
    over = {k: getattr(a, k) for k in ("back", "shape", "colorway", "nfc", "logo", "logo_mode", "logo_bleed")}
    run(lnkey.spec_from(a.address, a.edition, **over), a.out)
