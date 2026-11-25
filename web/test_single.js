// The one-filament tag: build it for a few backs, write the .3mf (for verify.py) and the .stl.
const fs = require('fs');
globalThis.qrcode = require('qrcode-generator'); globalThis.earcut = require('earcut');
const L = require('./engine.js');
const images = JSON.parse(fs.readFileSync('images.json')), badge = JSON.parse(fs.readFileSync('ekasi.json'));
const colors = { body: 'white', field: 'white', ink: 'black', accent: 'orange' };
fs.mkdirSync('out', { recursive: true });
const cases = [
  ['single-bitcoin', 'jasonbohio@blink.sv', images.find(i => i.id === 'bitcoin-coin')],
  ['single-trombone', 'jasonbohio@blink.sv', images.find(i => i.id === 'trombone')],
  ['single-ekasi', 'bitcoinekasi@blink.sv', badge],
  ['single-blank', 'a.very.long.name.for.testing@walletofsatoshi.com', null],
];
for (const [name, addr, img] of cases) {
  const tag = L.build({ address: addr, image: img, colors, method: 'single' });
  fs.writeFileSync(`out/${name}.3mf`, L.to3mf(tag, addr));
  fs.writeFileSync(`out/${name}.stl`, L.toSTL(tag.parts));
  fs.writeFileSync(`out/${name}.json`, JSON.stringify({ build: { payload: tag.payload, qr_version: tag.qr.version, qr_error: tag.qr.level, module_mm: 1.0, matrix: tag.qr.matrix } }));
  console.log(name, tag.width.toFixed(1) + ' x ' + tag.height.toFixed(1) + ' x ' + tag.thickness.toFixed(1), tag.grams.toFixed(2) + ' g',
    tag.parts.map(p => p.slot + ':' + p.colour + ' ' + p.grams.toFixed(2)).join(', '), 'swap at ' + tag.swap.z + ' mm, layer ' + tag.swap.layer);
}
