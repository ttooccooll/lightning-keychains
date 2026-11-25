/* lnkey web engine: Lightning address -> keychain geometry -> 3D preview data and a Bambu .3mf.
   Same design as the Python kit's flat "retail" tag: QR inlaid on the plate side, an image on the
   back, raised nothing, words nowhere. No server: everything runs in the page. */
(function (root) {
  'use strict';

  var P = {
    module: 1.0,        // QR module, mm
    rim: 1.8,           // rim width
    margin: 1.2,        // clear modules between the code's corners and the rim
    hole: 5.0,          // key-ring hole
    wall: 3.0,          // plastic round the hole
    fillet: 3.5,        // radius blending the loop into the tag
    collar: 1.6,
    T: 3.0,             // thickness
    layer: 0.2,
    faceLayers: 3,      // colour depth on each face (0.6 mm)
    bevel: [0.45, 0.25, 0.10]
  };
  var DENSITY = 1.24;   // PLA, g/cm3
  var LIGHT = { white: 1, cream: 1, yellow: 1 };

  function validAddress(a) { return /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test((a || '').trim()); }
  function payload(a) { return 'lightning:' + a.trim().toLowerCase(); }

  // ---- QR: smallest version that fits, then the strongest error correction that still fits ----
  function makeQR(text) {
    var qrcode = root.qrcode || require('qrcode-generator');
    var q = qrcode(0, 'M'); q.addData(text, 'Byte'); q.make();
    var n = q.getModuleCount(), type = (n - 17) / 4, level = 'M';
    ['Q', 'H'].some(function (lv) {
      try { var t = qrcode(type, lv); t.addData(text, 'Byte'); t.make(); q = t; level = lv; return false; }
      catch (e) { return true; }
    });
    var m = [];
    for (var r = 0; r < n; r++) { var row = []; for (var c = 0; c < n; c++) row.push(q.isDark(r, c) ? 1 : 0); m.push(row); }
    return { matrix: m, n: n, version: type, level: level };
  }

  // ---- trace a filled grid into boundary loops (filled on the right, y down) ----
  function traceGrid(get, w, h) {
    var out = new Map();                       // start vertex key -> [{x,y,dx,dy}]
    function add(x0, y0, x1, y1) {
      var k = x0 + ',' + y0, a = out.get(k);
      if (!a) { a = []; out.set(k, a); }
      a.push({ x: x1, y: y1, dx: x1 - x0, dy: y1 - y0, used: false });
    }
    for (var r = 0; r < h; r++) for (var c = 0; c < w; c++) {
      if (!get(c, r)) continue;
      if (!get(c, r - 1)) add(c, r, c + 1, r);
      if (!get(c + 1, r)) add(c + 1, r, c + 1, r + 1);
      if (!get(c, r + 1)) add(c + 1, r + 1, c, r + 1);
      if (!get(c - 1, r)) add(c, r + 1, c, r);
    }
    var loops = [];
    out.forEach(function (edges, key) {
      edges.forEach(function (e0) {
        if (e0.used) return;
        var p = key.split(',').map(Number), loop = [[p[0], p[1]]], e = e0;
        for (;;) {
          e.used = true;
          var nx = e.x, ny = e.y, cand = out.get(nx + ',' + ny), next = null;
          if (!cand) break;
          // where two cells meet corner to corner, turn right: each cell keeps its own loop
          var rdx = -e.dy, rdy = e.dx;
          for (var i = 0; i < cand.length; i++) if (!cand[i].used && cand[i].dx === rdx && cand[i].dy === rdy) { next = cand[i]; break; }
          if (!next) for (i = 0; i < cand.length; i++) if (!cand[i].used) { next = cand[i]; break; }
          if (!next) break;
          loop.push([nx, ny]);
          e = next;
        }
        if (loop.length >= 4) loops.push(loop);
      });
    });
    return loops.map(dropCollinear);
  }
  function dropCollinear(loop) {
    var n = loop.length, res = [];
    for (var i = 0; i < n; i++) {
      var a = loop[(i + n - 1) % n], b = loop[i], c = loop[(i + 1) % n];
      if ((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) !== 0) res.push(b);
    }
    return res;
  }
  // pull a rectilinear loop a hair into its filled side, so corner-touching shapes separate cleanly
  function insetRect(loop, d) {
    var n = loop.length, res = [];
    for (var i = 0; i < n; i++) {
      var a = loop[(i + n - 1) % n], b = loop[i], c = loop[(i + 1) % n];
      var d1x = Math.sign(b[0] - a[0]), d1y = Math.sign(b[1] - a[1]), d2x = Math.sign(c[0] - b[0]), d2y = Math.sign(c[1] - b[1]);
      res.push([b[0] + d * (-d1y - d2y), b[1] + d * (d1x + d2x)]);
    }
    return res;
  }
  function simplify(loop, tol) {                 // Ramer-Douglas-Peucker on a closed loop
    if (loop.length < 8) return loop;
    var far = 0, fi = 0;
    for (var i = 1; i < loop.length; i++) { var dd = dist2(loop[0], loop[i]); if (dd > far) { far = dd; fi = i; } }
    var a = rdp(loop.slice(0, fi + 1), tol), b = rdp(loop.slice(fi).concat([loop[0]]), tol);
    return a.slice(0, -1).concat(b.slice(0, -1));
  }
  function dist2(a, b) { var x = a[0] - b[0], y = a[1] - b[1]; return x * x + y * y; }
  function rdp(pts, tol) {
    var keep = new Uint8Array(pts.length), stack = [[0, pts.length - 1]]; keep[0] = keep[pts.length - 1] = 1;
    while (stack.length) {
      var s = stack.pop(), a = pts[s[0]], b = pts[s[1]], dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1e-9, md = 0, mi = -1;
      for (var i = s[0] + 1; i < s[1]; i++) { var d = Math.abs((pts[i][0] - a[0]) * dy - (pts[i][1] - a[1]) * dx) / len; if (d > md) { md = d; mi = i; } }
      if (md > tol) { keep[mi] = 1; stack.push([s[0], mi], [mi, s[1]]); }
    }
    return pts.filter(function (_, i) { return keep[i]; });
  }

  // ---- rings (even-odd, non-crossing) -> polygons with holes ----
  function ringArea(r) { var a = 0; for (var i = 0, n = r.length; i < n; i++) { var p = r[i], q = r[(i + 1) % n]; a += p[0] * q[1] - q[0] * p[1]; } return a / 2; }
  function inRing(pt, r) {
    var x = pt[0], y = pt[1], inside = false;
    for (var i = 0, j = r.length - 1; i < r.length; j = i++) {
      var xi = r[i][0], yi = r[i][1], xj = r[j][0], yj = r[j][1];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }
  function bbox(r) { var b = [1e9, 1e9, -1e9, -1e9]; r.forEach(function (p) { if (p[0] < b[0]) b[0] = p[0]; if (p[1] < b[1]) b[1] = p[1]; if (p[0] > b[2]) b[2] = p[0]; if (p[1] > b[3]) b[3] = p[1]; }); return b; }
  function ringsToPolys(rings) {
    var items = rings.filter(function (r) { return r.length >= 3; }).map(function (r) { return { r: r, a: Math.abs(ringArea(r)), b: bbox(r), depth: 0, parent: null }; });
    items = items.filter(function (it) { return it.a > 1e-6; });
    items.sort(function (p, q) { return q.a - p.a; });
    for (var i = 0; i < items.length; i++) {
      var it = items[i], pt = it.r[0];
      for (var j = i - 1; j >= 0; j--) {               // bigger rings only; nearest (smallest) container is the parent
        var o = items[j];
        if (pt[0] < o.b[0] || pt[0] > o.b[2] || pt[1] < o.b[1] || pt[1] > o.b[3]) continue;
        if (inRing(pt, o.r)) { it.depth++; if (!it.parent) it.parent = o; }
      }
    }
    var polys = [];
    items.forEach(function (it) { if (it.depth % 2 === 0) { it.poly = { outer: orient(it.r, true), holes: [] }; polys.push(it.poly); } });
    items.forEach(function (it) { if (it.depth % 2 === 1 && it.parent && it.parent.poly) it.parent.poly.holes.push(orient(it.r, false)); });
    return polys;
  }
  function orient(r, ccw) { return (ringArea(r) > 0) === ccw ? r : r.slice().reverse(); }
  function polyArea(p) { return Math.abs(ringArea(p.outer)) - p.holes.reduce(function (s, h) { return s + Math.abs(ringArea(h)); }, 0); }

  // ---- extrude a polygon with holes into a closed prism ----
  function prism(poly, z0, z1) {
    var earcut = root.earcut || require('earcut'); if (earcut.default) earcut = earcut.default;
    var flat = [], holes = [], rings = [poly.outer].concat(poly.holes), starts = [];
    // Edges of different rings often lie on one straight line (QR modules share grid lines). The
    // triangulator drops points it sees as exactly collinear, which would leave the caps and the
    // walls disagreeing about the edges. A repeatable nudge of about a micron prevents that.
    rings.forEach(function (r, i) {
      if (i) holes.push(flat.length / 2); starts.push(flat.length / 2);
      r.forEach(function (p) {
        var h1 = Math.sin(p[0] * 12.9898 + p[1] * 78.233) * 43758.5453, h2 = Math.sin(p[0] * 39.3467 + p[1] * 11.135) * 24634.6345;
        flat.push(p[0] + ((h1 - Math.floor(h1)) - 0.5) * 0.003, p[1] + ((h2 - Math.floor(h2)) - 0.5) * 0.003);
      });
    });
    var n = flat.length / 2, tri = earcut(flat, holes), verts = new Float32Array(n * 6), tris = [];
    for (var i = 0; i < n; i++) { verts.set([flat[2 * i], flat[2 * i + 1], z0], 3 * i); verts.set([flat[2 * i], flat[2 * i + 1], z1], 3 * (n + i)); }
    // earcut winds every triangle the same way; find which way once (zero-area slivers at its
    // hole bridges have no direction of their own and must follow the rest)
    var sum = 0;
    for (i = 0; i < tri.length; i += 3) {
      var a = tri[i], b = tri[i + 1], c = tri[i + 2];
      sum += (flat[2 * b] - flat[2 * a]) * (flat[2 * c + 1] - flat[2 * a + 1]) - (flat[2 * b + 1] - flat[2 * a + 1]) * (flat[2 * c] - flat[2 * a]);
    }
    for (i = 0; i < tri.length; i += 3) {
      a = tri[i]; b = tri[i + 1]; c = tri[i + 2];
      if (sum < 0) { var t = b; b = c; c = t; }
      tris.push(n + a, n + b, n + c, a, c, b);              // top faces up, bottom faces down
    }
    rings.forEach(function (r, ri) {
      var s = starts[ri], m = r.length;
      for (var k = 0; k < m; k++) { var p = s + k, q = s + (k + 1) % m; tris.push(p, q, n + q, p, n + q, n + p); }
    });
    return { verts: verts, tris: tris };
  }

  // ---- the tag's outline: disc + loop, blended with fillets; d sets the edge back (bevel) ----
  function outline(R, d) {
    var hr = P.hole / 2, r1 = hr + P.wall, cy = R + Math.max(hr + 0.3, hr + P.collar - P.rim), rf = P.fillet;
    var A = R + rf, B = r1 + rf, fy = (A * A - B * B + cy * cy) / (2 * cy), fx = Math.sqrt(A * A - fy * fy);
    var t0 = Math.atan2(fy, fx), t1 = Math.atan2(fy - cy, fx), phi = Math.atan2(cy - fy, -fx);
    var pts = [];
    function arc(cx, cyy, r, a0, a1, n) { for (var i = 0; i < n; i++) { var a = a0 + (a1 - a0) * i / n; pts.push([cx + r * Math.cos(a), cyy + r * Math.sin(a)]); } }
    arc(0, 0, R - d, Math.PI - t0, 2 * Math.PI + t0, 200);        // round the body, anticlockwise
    arc(fx, fy, rf + d, t0 + Math.PI, phi, 18);                   // right fillet (concave)
    arc(0, cy, r1 - d, t1, Math.PI - t1, 56);                     // over the loop
    arc(-fx, fy, rf + d, Math.PI - phi, -t0, 18);                 // left fillet
    var hole = [];
    for (var i = 0; i < 48; i++) { var a = 2 * Math.PI * i / 48; hole.push([(hr + d) * Math.cos(a), cy + (hr + d) * Math.sin(a)]); }
    return { ring: pts, hole: hole, cy: cy, top: cy + r1 };
  }
  function circle(r, n) { var c = []; for (var i = 0; i < n; i++) { var a = 2 * Math.PI * i / n; c.push([r * Math.cos(a), r * Math.sin(a)]); } return c; }

  // ---- build ----
  function build(opts) {
    // opts: {address, image, colors:{body, field, ink, accent}}  (colour names)
    // image is {rings} - a one-colour picture, grown to fill the field - or a badge
    // {badge:true, cut, light, accent}: a round logo that takes over the whole back of the tag.
    var col = opts.colors, text = opts.payload || payload(opts.address), qr = makeQR(text), n = qr.n, m = P.module;
    var half = n * m / 2, fieldR = half * Math.SQRT2 + P.margin * m, R = fieldR + P.rim;
    var o0 = outline(R, 0);

    // QR dark shapes in mm (as you look at the code), a hair inside their nominal edges
    var dark = traceGrid(function (c, r) { return r >= 0 && c >= 0 && r < n && c < n && qr.matrix[r][c]; }, n, n)
      .map(function (l) { return insetRect(l, 0.01).map(function (p) { return [(p[0] - n / 2) * m, (n / 2 - p[1]) * m]; }); });
    var darkPlate = dark.map(function (l) { return l.map(function (p) { return [-p[0], p[1]]; }); });   // mirrored: it prints face-down

    // back image, as large as its shape allows
    var img = [], badge = null;
    if (opts.image && opts.image.badge) {
      var kb = 2 * R, sc = function (rs) { return (rs || []).map(function (r) { return r.map(function (p) { return [p[0] * kb, p[1] * kb]; }); }); };
      badge = { cut: sc(opts.image.cut), light: sc(opts.image.light), accent: sc(opts.image.accent) };
    } else if (opts.image && opts.image.rings && opts.image.rings.length) {
      var far = 0; opts.image.rings.forEach(function (r) { r.forEach(function (p) { var d = Math.hypot(p[0], p[1]); if (d > far) far = d; }); });
      var k = (fieldR - 1.4) * 0.97 / far * (opts.imageScale || 1);
      img = opts.image.rings.map(function (r) { return r.map(function (p) { return [p[0] * k, p[1] * k]; }); });
    }

    var lightOverDark = col.field !== col.body && LIGHT[col.field];
    var fl = lightOverDark ? 5 : P.faceLayers, nl = Math.round(P.T / P.layer);
    var parts = {}, order = [];
    function part(colour) { if (!parts[colour]) { parts[colour] = { colour: colour, prisms: [], volume: 0 }; order.push(colour); } return parts[colour]; }
    function put(colour, rings, z0, z1) {
      ringsToPolys(rings).forEach(function (p) { var a = polyArea(p); if (a < 0.01) return; var pt = part(colour); pt.prisms.push(prism(p, z0, z1)); pt.volume += a * (z1 - z0); });
    }
    part(col.body);
    var field = circle(fieldR, 160);
    var k0 = 0;
    while (k0 < nl) {
      var zone = k0 < fl ? 'front' : (k0 >= nl - fl ? 'back' : 'core');
      var inset = Math.max(k0 < P.bevel.length ? P.bevel[k0] : 0, nl - 1 - k0 < P.bevel.length ? P.bevel[nl - 1 - k0] : 0);
      var k1 = k0 + 1;                                       // merge identical neighbouring layers into one slab
      while (k1 < nl) {
        var z2 = k1 < fl ? 'front' : (k1 >= nl - fl ? 'back' : 'core');
        var i2 = Math.max(k1 < P.bevel.length ? P.bevel[k1] : 0, nl - 1 - k1 < P.bevel.length ? P.bevel[nl - 1 - k1] : 0);
        if (z2 !== zone || i2 !== inset) break; k1++;
      }
      var z0 = k0 * P.layer, z1 = k1 * P.layer, o = inset ? outline(R, inset) : o0;
      if (zone === 'core') {
        put(col.body, [o.ring, o.hole], z0, z1);
      } else if (zone === 'back' && badge) {
        put(col.ink, [o.ring, o.hole].concat(badge.cut), z0, z1);                       // the badge's face, edge to edge
        put(col.field, badge.light, z0, z1);
        put(col.accent, badge.accent, z0, z1);
      } else {
        put(col.ink, [o.ring, o.hole, field], z0, z1);                                  // the rim and the loop
        if (zone === 'front') {
          put(col.ink, darkPlate, z0, z1);
          put(col.field, [field].concat(darkPlate), z0, z1);
        } else {
          if (img.length) put(col.accent, img, z0, z1);
          put(col.field, [field].concat(img), z0, z1);
        }
      }
      k0 = k1;
    }
    var slots = [];
    [col.body, col.field, col.ink, col.accent].forEach(function (c) { if (parts[c] && parts[c].prisms.length && slots.indexOf(c) < 0) slots.push(c); });
    var list = slots.map(function (c, i) { var p = parts[c]; p.slot = i + 1; p.grams = p.volume / 1000 * DENSITY; return p; });
    return {
      parts: list, payload: text, qr: qr, R: R, fieldR: fieldR, width: 2 * R, height: o0.top + R, thickness: P.T,
      loopY: o0.cy, grams: list.reduce(function (s, p) { return s + p.grams; }, 0), outline: o0, dark: dark, image: img
    };
  }

  // flat triangle soup for a renderer: Float32Array of xyz per part
  function soup(p) {
    var count = p.prisms.reduce(function (s, pr) { return s + pr.tris.length; }, 0), out = new Float32Array(count * 3), o = 0;
    p.prisms.forEach(function (pr) { for (var i = 0; i < pr.tris.length; i++) { var v = pr.tris[i] * 3; out[o++] = pr.verts[v]; out[o++] = pr.verts[v + 1]; out[o++] = pr.verts[v + 2]; } });
    return out;
  }

  // ---- .3mf (a zip): Bambu Studio project flavour, one part per filament ----
  function to3mf(tag, name) {
    var objs = [], comps = [], cfg = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>'], oid = 0, parts = [], faces = 0;
    tag.parts.forEach(function (p) {
      oid++;
      var xml = ['<object id="' + oid + '" type="model"><mesh><vertices>'], tri = [], off = 0;
      p.prisms.forEach(function (pr) {
        for (var i = 0; i < pr.verts.length; i += 3) xml.push('<vertex x="' + pr.verts[i].toFixed(4) + '" y="' + pr.verts[i + 1].toFixed(4) + '" z="' + pr.verts[i + 2].toFixed(4) + '"/>');
        for (i = 0; i < pr.tris.length; i += 3) tri.push('<triangle v1="' + (pr.tris[i] + off) + '" v2="' + (pr.tris[i + 1] + off) + '" v3="' + (pr.tris[i + 2] + off) + '"/>');
        off += pr.verts.length / 3;
      });
      faces += tri.length;
      xml.push('</vertices><triangles>', tri.join(''), '</triangles></mesh></object>');
      objs.push(xml.join(''));
      comps.push('<component objectid="' + oid + '" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>');
      parts.push('    <part id="' + oid + '" subtype="normal_part">\n      <metadata key="name" value="' + p.colour + ' (' + p.colour + ')"/>\n' +
        '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n      <metadata key="extruder" value="' + p.slot + '"/>\n    </part>');
    });
    oid++;
    objs.push('<object id="' + oid + '" type="model"><components>' + comps.join('') + '</components></object>');
    var safe = esc(name || tag.payload);
    cfg.push('  <object id="' + oid + '">\n    <metadata key="name" value="' + safe + '"/>\n    <metadata key="extruder" value="1"/>\n' +
      '    <metadata key="wall_loops" value="5"/>\n    <metadata key="sparse_infill_density" value="100%"/>\n' +
      '    <metadata key="top_shell_layers" value="5"/>\n    <metadata key="bottom_shell_layers" value="5"/>\n' +
      '    <metadata face_count="' + faces + '"/>\n' + parts.join('\n') + '\n  </object>', '</config>');
    var model = '<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" ' +
      'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">\n <metadata name="Application">BambuStudio-01.09.00.70</metadata>\n' +
      ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <metadata name="Title">' + safe + '</metadata>\n <resources>\n' + objs.join('\n') +
      '\n </resources>\n <build>\n<item objectid="' + oid + '" transform="1 0 0 0 1 0 0 0 1 128 128 0" printable="1"/>\n </build>\n</model>\n';
    var types = '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n' +
      ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n' +
      ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n <Default Extension="config" ContentType="text/xml"/>\n</Types>\n';
    var rels = '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n' +
      ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n';
    return zip([['[Content_Types].xml', types], ['_rels/.rels', rels], ['3D/3dmodel.model', model], ['Metadata/model_settings.config', cfg.join('\n')]]);
  }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  // minimal zip writer (stored, no compression)
  var CRC = (function () { var t = new Uint32Array(256); for (var n = 0; n < 256; n++) { var c = n; for (var k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  function crc32(b) { var c = 0xFFFFFFFF; for (var i = 0; i < b.length; i++) c = CRC[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
  function utf8(s) { if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(s); return Uint8Array.from(Buffer.from(s, 'utf8')); }
  function zip(files) {
    var chunks = [], central = [], offset = 0;
    files.forEach(function (f) {
      var name = utf8(f[0]), data = typeof f[1] === 'string' ? utf8(f[1]) : f[1], crc = crc32(data), h = new DataView(new ArrayBuffer(30));
      h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x0800, true); h.setUint16(8, 0, true); h.setUint16(10, 0, true); h.setUint16(12, 0x21, true);
      h.setUint32(14, crc, true); h.setUint32(18, data.length, true); h.setUint32(22, data.length, true); h.setUint16(26, name.length, true); h.setUint16(28, 0, true);
      chunks.push(new Uint8Array(h.buffer), name, data);
      var c = new DataView(new ArrayBuffer(46));
      c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(8, 0x0800, true); c.setUint16(10, 0, true); c.setUint16(12, 0, true); c.setUint16(14, 0x21, true);
      c.setUint32(16, crc, true); c.setUint32(20, data.length, true); c.setUint32(24, data.length, true); c.setUint16(28, name.length, true); c.setUint32(42, offset, true);
      central.push(new Uint8Array(c.buffer), name);
      offset += 30 + name.length + data.length;
    });
    var csize = central.reduce(function (s, a) { return s + a.length; }, 0), e = new DataView(new ArrayBuffer(22));
    e.setUint32(0, 0x06054b50, true); e.setUint16(8, files.length, true); e.setUint16(10, files.length, true); e.setUint32(12, csize, true); e.setUint32(16, offset, true);
    var all = chunks.concat(central, [new Uint8Array(e.buffer)]), total = all.reduce(function (s, a) { return s + a.length; }, 0), out = new Uint8Array(total), o = 0;
    all.forEach(function (a) { out.set(a, o); o += a.length; });
    return out;
  }

  // ---- a picture (RGBA pixels) -> image rings, for "use your own logo" ----
  function traceImage(rgba, w, h) {
    var transparent = 0, i, total = w * h;
    for (i = 0; i < total; i++) if (rgba[4 * i + 3] < 128) transparent++;
    var hasAlpha = transparent / total > 0.01, mask = new Uint8Array(total), dark = 0, opaque = 0;
    for (i = 0; i < total; i++) {
      if (rgba[4 * i + 3] < 128) continue; opaque++;
      var lum = (0.2126 * rgba[4 * i] + 0.7152 * rgba[4 * i + 1] + 0.0722 * rgba[4 * i + 2]) / 255;
      if (lum < (hasAlpha ? 0.8 : 0.6)) { mask[i] = 1; dark++; }
    }
    if (hasAlpha && dark / total < 0.005) for (i = 0; i < total; i++) mask[i] = rgba[4 * i + 3] >= 128 ? 1 : 0;   // a light logo on transparency: use its shape
    var loops = traceGrid(function (c, r) { return c >= 0 && r >= 0 && c < w && r < h && mask[r * w + c]; }, w, h)
      .map(function (l) { return simplify(insetRect(l, 0.02), 0.7); }).filter(function (l) { return l.length >= 3 && Math.abs(ringArea(l)) > 6; });
    if (!loops.length) return null;
    var b = [1e9, 1e9, -1e9, -1e9]; loops.forEach(function (l) { var bb = bbox(l); b = [Math.min(b[0], bb[0]), Math.min(b[1], bb[1]), Math.max(b[2], bb[2]), Math.max(b[3], bb[3])]; });
    var s = 1 / Math.max(b[2] - b[0], b[3] - b[1]), cx = (b[0] + b[2]) / 2, cyy = (b[1] + b[3]) / 2;
    return { rings: loops.map(function (l) { return l.map(function (p) { return [(p[0] - cx) * s, (cyy - p[1]) * s]; }); }) };
  }

  var api = { P: P, validAddress: validAddress, payload: payload, makeQR: makeQR, build: build, soup: soup, to3mf: to3mf, zip: zip, traceImage: traceImage, ringsToPolys: ringsToPolys, traceGrid: traceGrid };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.LNKEY = api;
})(typeof window !== 'undefined' ? window : globalThis);
