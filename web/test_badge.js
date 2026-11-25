const fs = require('fs');
globalThis.qrcode = require('qrcode-generator'); globalThis.earcut = require('earcut');
const L = require('./engine.js');
const badge = JSON.parse(fs.readFileSync('ekasi.json'));
const images = JSON.parse(fs.readFileSync('images.json'));
fs.mkdirSync('out', { recursive: true });
const cases = [
  ['web-ekasi-badge', 'bitcoinekasi@blink.sv', badge, { body: 'white', field: 'white', ink: 'black', accent: 'orange' }],
  ['web-ekasi-badge-midnight', 'bitcoinekasi@blink.sv', badge, { body: 'black', field: 'white', ink: 'black', accent: 'orange' }],
  ['web-bitcoin', 'jasonbohio@blink.sv', images.find(i => i.id === 'bitcoin-coin'), { body: 'white', field: 'white', ink: 'black', accent: 'orange' }],
  ['web-surf', 'jasonbohio@blink.sv', images.find(i => i.id === 'surfing'), { body: 'white', field: 'white', ink: 'black', accent: 'black' }],
];
for (const [name, addr, img, colors] of cases) {
  const t0 = Date.now(), tag = L.build({ address: addr, image: img, colors }), bytes = L.to3mf(tag, addr);
  fs.writeFileSync(`out/${name}.3mf`, bytes);
  fs.writeFileSync(`out/${name}.json`, JSON.stringify({ build: { payload: tag.payload, qr_version: tag.qr.version, qr_error: tag.qr.level, module_mm: 1.0, matrix: tag.qr.matrix } }));
  console.log(name, tag.grams.toFixed(2) + ' g', tag.parts.map(p => p.slot + ':' + p.colour + ' ' + p.grams.toFixed(2)).join(', '), (bytes.length / 1024).toFixed(0) + ' KB', (Date.now() - t0) + ' ms');
}
