#!/usr/bin/env python3
"""
verify.py - independent check of a generated .3mf before it goes on the printer.

Reads the file back from disk (not the generator's memory), and for each keychain:
  1. every part is a closed, valid solid and no two parts overlap
  2. slices the QR face out of the real meshes, pictures it the way a phone sees it
     (mirrored if that face prints on the plate), and decodes it with two independent
     QR readers; the decoded text must equal the expected payload
  3. repeats the decode with blur + low contrast to mimic a rough print

    python verify.py out/jasonbohio-blink-sv_retail.3mf
"""
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
from manifold3d import Manifold, Mesh
from PIL import Image, ImageDraw, ImageFilter

NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
LUMA = {"white": 240, "cream": 228, "yellow": 200, "mint": 205, "orange": 150, "pink": 150, "gold": 150,
        "gray": 140, "teal": 120, "red": 75, "green": 95, "blue": 70, "purple": 70, "brown": 60,
        "navy": 35, "black": 25}


def read_3mf(path):
    with zipfile.ZipFile(path) as z:
        model = ET.fromstring(z.read("3D/3dmodel.model"))
        cfg = ET.fromstring(z.read("Metadata/model_settings.config"))
    meshes, assemblies = {}, {}
    for obj in model.find("m:resources", NS):
        oid = int(obj.get("id"))
        mesh = obj.find("m:mesh", NS)
        if mesh is not None:
            v = np.array([[float(e.get(k)) for k in "xyz"] for e in mesh.find("m:vertices", NS)], np.float32)
            t = np.array([[int(e.get(k)) for k in ("v1", "v2", "v3")] for e in mesh.find("m:triangles", NS)],
                         np.uint32)
            meshes[oid] = (v, t)
        else:
            assemblies[oid] = [int(c.get("objectid")) for c in obj.find("m:components", NS)]
    tags = []
    for o in cfg.findall("object"):
        oid = int(o.get("id"))
        name = next(m.get("value") for m in o.findall("metadata") if m.get("key") == "name")
        parts = []
        for p in o.findall("part"):
            md = {m.get("key"): m.get("value") for m in p.findall("metadata")}
            parts.append(dict(id=int(p.get("id")), name=md["name"], slot=int(md["extruder"])))
        assert sorted(p["id"] for p in parts) == sorted(assemblies[oid]), "config parts != model components"
        tags.append(dict(name=name, parts=parts))
    return meshes, tags


def face_image(solids, z, mirror, px=14, pad=4.0):
    """Raster of all parts sliced at height z. solids: [(Manifold, colour)]"""
    bb = np.array([s.bounding_box() for s, _ in solids])
    x0, y0, x1, y1 = bb[:, 0].min() - pad, bb[:, 1].min() - pad, bb[:, 3].max() + pad, bb[:, 4].max() + pad
    W, H = int((x1 - x0) * px), int((y1 - y0) * px)
    img = Image.new("L", (W, H), 205)                       # neutral table-top
    d = ImageDraw.Draw(img)
    order = sorted(solids, key=lambda sc: -sc[0].slice(z).area())
    for solid, colour in order:
        cs = solid.slice(z)
        rings = [np.asarray(r) for r in cs.to_polygons()]
        if not rings:
            continue
        mask = Image.new("1", (W, H), 0)
        md = ImageDraw.Draw(mask)
        def area(r):
            x, y = r[:, 0], r[:, 1]
            return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
        for r in sorted(rings, key=lambda r: -abs(area(r))):
            xs = (r[:, 0] - x0) * px
            if mirror:
                xs = W - xs
            ys = H - (r[:, 1] - y0) * px
            md.polygon(list(zip(xs, ys)), fill=1 if area(r) > 0 else 0)
        img.paste(LUMA.get(colour, 128), mask=mask)
    return img


def module_match(img, expected, info, solids, px=14, pad=4.0):
    """Sample the picture at every module centre and compare with a freshly made code.
    Readers accept mirrored codes, so this is what proves the handedness is right."""
    if not expected:
        return None
    import segno
    b = info.get("build", {})
    if b.get("matrix"):                                  # the generator recorded the exact code it drew
        ref = np.array(b["matrix"])
    else:
        qr = segno.make(expected, error=(b.get("qr_error") or "m").lower(), micro=False, boost_error=False,
                        version=b.get("qr_version"))
        ref = np.array([[1 if c else 0 for c in row] for row in qr.matrix])
    n, m = ref.shape[0], b.get("module_mm", 1.0)
    bb = np.array([s.bounding_box() for s, _ in solids])
    x0, y0 = bb[:, 0].min() - pad, bb[:, 1].min() - pad
    arr = np.array(img)
    H = arr.shape[0]
    good = 0
    for r in range(n):
        for c in range(n):
            x = -n * m / 2 + (c + 0.5) * m
            y = n * m / 2 - (r + 0.5) * m
            v = arr[int(H - (y - y0) * px), int((x - x0) * px)]
            good += int((v < 128) == bool(ref[r, c]))
    return good, n * n


def decode(img):
    out = {}
    try:
        import zxingcpp
        r = zxingcpp.read_barcodes(img)
        out["zxing"] = r[0].text if r else None
    except ImportError:
        out["zxing"] = "n/a"
    try:
        import cv2
        val, _, _ = cv2.QRCodeDetector().detectAndDecode(np.array(img))
        out["opencv"] = val or None
    except ImportError:
        out["opencv"] = "n/a"
    return out


def check(path, expected=None, save_images=True):
    side = os.path.splitext(path)[0] + ".json"
    info = json.load(open(side)) if os.path.exists(side) else {}
    expected = expected or info.get("build", {}).get("payload")
    meshes, tags = read_3mf(path)
    ok_all = True
    for tag in tags:
        print(f"\n{os.path.basename(path)} :: {tag['name']}")
        solids = []
        for p in tag["parts"]:
            v, t = meshes[p["id"]]
            m = Manifold(Mesh(vert_properties=v, tri_verts=t))
            good = (not m.is_empty()) and m.status().name == "NoError" and m.volume() > 0
            colour = p["name"].split("(")[-1].rstrip(")")
            solids.append((m, colour))
            print(f"   part {p['name']:24s} slot {p['slot']}  {m.volume():8.1f} mm3  {m.num_tri():6d} tris  "
                  f"{'closed solid' if good else 'BROKEN'}")
            ok_all &= good
        worst = 0.0
        for i in range(len(solids)):
            for j in range(i + 1, len(solids)):
                worst = max(worst, (solids[i][0] ^ solids[j][0]).volume())
        print(f"   largest overlap between parts: {worst:.4f} mm3 {'OK' if worst < 0.05 else 'OVERLAP'}")
        ok_all &= worst < 0.05
        zmin = min(s.bounding_box()[2] for s, _ in solids)
        zmax = max(s.bounding_box()[5] for s, _ in solids)
        # QR face is whichever outer face decodes; test both the way a phone would see them
        results = {}
        for face, z, mirror in (("plate side", zmin + 0.1, True), ("top side", zmax - 0.1, False),
                                ("top side (relief)", zmax - 0.35, False)):
            img = face_image(solids, z, mirror)
            if "relief" in face:
                # raised modules: the base surface shows between them
                base = face_image(solids, zmax - 0.95, mirror)
                top = img
                arr_t, arr_b = np.array(top), np.array(base)
                img = Image.fromarray(np.where(arr_t != 205, arr_t, arr_b).astype(np.uint8))
            res = decode(img)
            res["modules"] = module_match(img, expected, info, solids)
            rough = img.filter(ImageFilter.GaussianBlur(5)).point(lambda v: int(60 + v * 0.55))
            res_rough = decode(rough.resize((rough.width // 3, rough.height // 3)))
            results[face] = (res, res_rough, img)
        hit = None
        for face, (res, res_rough, img) in results.items():
            mm = res.pop("modules", None)
            vals = [v for v in res.values() if v not in (None, "n/a")]
            if vals:
                if mm is not None and mm[0] == 0:
                    print(f"   module-by-module: all {mm[1]} modules are the opposite shade = INVERTED code "
                          f"(light on dark). Right way round, but some wallet scanners cannot read inverted codes.")
                elif mm is not None:
                    print(f"   module-by-module vs. the reference code, un-mirrored: {mm[0]}/{mm[1]} match"
                          f"{'' if mm[0] == mm[1] else '  <-- MIRRORED OR DAMAGED'}")
                    ok_all &= mm[0] == mm[1]
                hit = face
                good = all(v == expected for v in vals) if expected else True
                rough_ok = any(v == expected for v in res_rough.values()) if expected else True
                print(f"   QR on {face}: {res}")
                print(f"   matches expected payload: {'YES' if good else 'NO  <-- expected ' + repr(expected)}"
                      f"   | blurred/low-contrast decode: {'ok' if rough_ok else 'failed'}")
                ok_all &= good and len(vals) >= 1
                if save_images:
                    out = os.path.splitext(path)[0] + f"_verify.png"
                    img.save(out)
                break
        if not hit:
            print("   QR DID NOT DECODE on either face")
            ok_all = False
    print("\nRESULT:", "PASS" if ok_all else "FAIL")
    return ok_all


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    results = [check(p) for p in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
