// Assembles dist/index.html: the page with the QR library, the triangulator, the engine and the pictures inlined.
const fs = require('fs');
let html = fs.readFileSync('index.src.html', 'utf8');
const safe = s => s.replace(/<\/script/gi, '<\\/script');
const put = (mark, text) => { if (!html.includes(mark)) throw new Error('missing ' + mark); html = html.split(mark).join(text); };
put('/*__QRCODE__*/', safe(fs.readFileSync('node_modules/qrcode-generator/dist/qrcode.js', 'utf8')));
put('/*__EARCUT__*/', safe(fs.readFileSync('node_modules/earcut/dist/earcut.min.js', 'utf8')));
put('/*__ENGINE__*/', safe(fs.readFileSync('engine.js', 'utf8')));
put('/*__IMAGES__*/[]', fs.readFileSync('images.json', 'utf8').replace(/</g, '\\u003c'));
put('/*__EKASI__*/null', fs.existsSync('ekasi.json') ? fs.readFileSync('ekasi.json', 'utf8').replace(/</g, '\\u003c') : 'null');
fs.mkdirSync('dist', { recursive: true });
fs.writeFileSync('dist/index.html', html);
console.log('dist/index.html', (html.length / 1024).toFixed(0) + ' KB');
