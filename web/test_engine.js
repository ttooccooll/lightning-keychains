const fs = require('fs');
globalThis.qrcode = require('qrcode-generator'); globalThis.earcut = require('earcut');
const L = require('./engine.js');
const images = JSON.parse(fs.readFileSync('images.json'));
const cases = [
  ['web-classic', 'jasonbohio@blink.sv', 'bitcoin-coin', { body: 'white', field: 'white', ink: 'black', accent: 'orange' }],
  ['web-ekasi', 'bitcoinekasi@blink.sv', 'surfing', { body: 'white', field: 'white', ink: 'black', accent: 'black' }],
  ['web-midnight', 'milani@blink.sv', 'trombone', { body: 'black', field: 'white', ink: 'black', accent: 'orange' }],
  ['web-long', 'a.very.long.name.for.testing@walletofsatoshi.com', 'coffee', { body: 'orange', field: 'orange', ink: 'black', accent: 'white' }],
];
fs.mkdirSync('out', { recursive: true });
for (const [name, addr, img, colors] of cases) {
  const t0 = Date.now();
  const tag = L.build({ address: addr, image: images.find(i => i.id === img), colors });
  const bytes = L.to3mf(tag, addr);
  fs.writeFileSync(`out/${name}.3mf`, bytes);
  fs.writeFileSync(`out/${name}.json`, JSON.stringify({ build: { payload: tag.payload, qr_version: tag.qr.version, qr_error: tag.qr.level, module_mm: 1.0, matrix: tag.qr.matrix } }));
  console.log(name, 'v' + tag.qr.version + '-' + tag.qr.level, tag.width.toFixed(1) + ' x ' + tag.height.toFixed(1), tag.grams.toFixed(2) + ' g',
    tag.parts.map(p => p.slot + ':' + p.colour + ' ' + p.grams.toFixed(2)).join(', '), (bytes.length / 1024).toFixed(0) + ' KB', (Date.now() - t0) + ' ms');
}
// traced picture: a ring with a dot, on transparency
const w = 96, h = 96, px = new Uint8ClampedArray(w * h * 4);
for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const d = Math.hypot(x - 48, y - 48); if ((d < 44 && d > 30) || d < 12) px.set([20, 20, 20, 255], 4 * (y * w + x)); }
const traced = L.traceImage(px, w, h);
console.log('traced rings', traced.rings.length, traced.rings.map(r => r.length).join(','));
const t2 = L.build({ address: 'jasonbohio@blink.sv', image: traced, colors: cases[0][3] });
fs.writeFileSync('out/web-traced.3mf', L.to3mf(t2, 'traced'));
fs.writeFileSync('out/web-traced.json', JSON.stringify({ build: { payload: t2.payload, qr_version: t2.qr.version, qr_error: t2.qr.level, module_mm: 1.0, matrix: t2.qr.matrix } }));
