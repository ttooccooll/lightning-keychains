# lnkey: Lightning-address keychains for the Bambu A1 + AMS lite

Type a Lightning address, get a multi-colour Bambu Studio project: the QR code on one side, one
big picture on the other. No words on either side.

There are two ways in:

- **The website** (`web/index.html`): anyone types their address, picks a picture or uploads
  their logo, picks colours and downloads the print file. Nothing to install. See "The website".
- **The command line** (`lnkey.py`): the same tag plus the other editions, plates of 19, NFC
  pockets and CSV batches for orders.

```
pip install -r requirements.txt
python lnkey.py jasonbohio@blink.sv --edition retail --back btc
python verify.py out/jasonbohio-blink-sv_retail.3mf
```

Each run writes, next to the `.3mf`:

| file | what it is for |
|---|---|
| `*_preview.png` | both faces as they will look |
| `*_qr-test.png` | the exact code as a flat image. Scan it off your screen with 3 or 4 wallets before printing |
| `*.json` | size, grams per colour, colour changes, the QR payload |
| `*_N-colour.stl` (`--stl`) | one STL per colour, for slicers other than Bambu Studio |

## The three editions

| | `meetup` | `retail` | `ekasi` |
|---|---|---|---|
| Look | raised QR and rim, blank back | flat coin, QR inlaid flush, picture on the back | raised QR and rim (the Mossel Bay design) with Bitcoin Ekasi's logo filling the back |
| Prints | QR up | **QR down, on the plate** | QR up, back on the plate |
| Colours | 2 | 2–4 | 3 |
| Colour changes per plate | 1 | about 10 | about 7 |
| Plastic per tag | 5.3 g | 6.6 g | 5.3 g |
| Size (this address) | 47 × 55 × 2.8 mm | 47 × 55 × 3.0 mm | 47 × 55 × 2.8 mm |

The QR side carries the code and the rim and nothing else. The back carries one picture, grown
until it nearly touches the rim. There is no lettering anywhere on the tag.

Colour changes are counted per *plate*, not per tag: 19 round tags (or 29 square ones) share the
same handful of changes. Print full plates and the purge waste all but disappears.

Everything an edition sets can be overridden: `--shape square`, `--style flush|relief`,
`--colorway`, `--back`, `--logo`, `--nfc`, `--module 1.1`, `--payload lnurl`.

## The loop

The loop is where thin tags snap, so it is built not to:

- 3.0 mm of plastic all the way round a 5 mm hole (`loop_wall`, `hole` in the `Spec`).
- It sits as low on the tag as the rim allows and blends into the body through 3.5 mm fillets,
  so there is no sharp inside corner for a crack to start from. Where it meets the tag it is
  12 mm wide.
- It is the full thickness of the tag, and on the raised editions it stands at rim height.
- The project file asks the slicer for 5 walls and 100% infill, so the loop is solid plastic.
  Check that these arrived (Objects list → the tag → its settings); if not, set them once in
  your process profile.

Thread the split ring by opening it with a staple remover or a coin rather than levering it
against the plastic.

## Pictures for the back

| `--back` | picture |
|---|---|
| `btc` | the Bitcoin mark knocked out of a coin |
| `bolt` | a lightning bolt |
| `sats` | the sats symbol |
| `pill` | an orange pill |
| `zap` | a bolt in a ring |
| `tipjar` | a jar with a bolt on it |
| `miner` | a home miner that heats the room |
| `surf` | a surfer |
| `trombone`, `coffee`, `foodtruck`, `barber`, `pets`, `eggs` … | trades, shops and hobbies |

- `python lnkey.py --list-icons coffee` searches the built-in pictures. About 100 have friendly
  names; any of the 7,400 Material Design Icons file names also works (`--back saxophone`).
- A customer's logo: `--logo path/to/logo.svg` (or `.png` / `.jpg`). See "Logos" below.
- `python catalog.py` redraws the catalogue sheet.

The generator warns when a picture has details thinner than 0.4 mm.

## Logos

```
python lnkey.py owner@wallet.com --edition retail --logo their-logo.svg
python lnkey.py owner@wallet.com --edition retail --logo their-logo.png --logo-mode color
python lnkey.py owner@wallet.com --edition retail --logo round-badge.svg --logo-mode color --logo-bleed
python lnkey.py bitcoinekasi@blink.sv --edition ekasi
```

- **SVG** is best. Filled shapes, strokes, groups and transforms are all read, in paint order, so
  white details drawn on top of dark shapes become cut-outs. Live text must be converted to
  outlines first; embedded pictures are ignored.
- **PNG / JPG** are traced. Transparent backgrounds work best; 600 px or more on the long side.
- `--logo-mode mono` (default) prints everything dark in the ink colour. `--logo-mode color` sends
  each colour in the artwork to the nearest of the colourway's field, ink and accent filaments.
- The logo is grown until it comes within 0.4 mm of the rim. `--logo-scale 0.9` shrinks it.
- `--logo-bleed` is for a round badge: its circle becomes the tag's circle, the rim is dropped
  and the loop takes the badge's outer colour, so the back of the tag is the badge.
- Details finer than 0.4 mm are fattened slightly; if they still will not print, the generator
  says so. Use the simplest version of the artwork you have (a one-colour mark, not the full
  lock-up with small type).
- `samples/logo-test/your-logo.svg` and `.png` are a stand-in used to test this path, and
  `samples/jasonbohio-your-logo_retail.3mf` is a tag built with it.

### Bitcoin Ekasi's logo

`logos/bitcoin-ekasi/` holds Bitcoin Ekasi's logo, used here with their permission. While those
files are in place the `ekasi` edition puts the logo edge to edge on the back, in white, black
and orange. `--back surf --colorway ekasi` gives the two-colour surfer version instead, and
without the files the edition falls back to it by itself.

Only put an organisation's logo on a tag when that organisation has asked for it or agreed to it.

## The website

`web/` is a one-page site: a visitor types a Lightning address, picks one of 24 pictures or
uploads a logo (traced to one colour), picks a colourway, turns the tag round in 3D and downloads
the `.3mf`. Everything happens in the visitor's browser; nothing is uploaded and there is no
server to run.

```
cd web
npm install
npm run build      # writes web/dist/index.html, the whole site in one file
npm test           # writes test files into web/out for verify.py
```

- It makes the retail tag: flat coin, QR face-down on the plate, picture on the back. The
  preview is drawn from the same solids that go into the file.
- Two addresses are set near the top of the script in `web/index.src.html`: `OWNER_ADDRESS`
  (shown until the visitor types their own) and `EKASI_ADDRESS`.
- "Load the Bitcoin Ekasi tag" shows their logo on the back with their address on the front.
  The logo stays with that address: when the visitor types another one, the picture goes back
  to the one they had, and only the colourways that keep the logo black, white and orange stay
  open while it is showing.
- `python tools/make_web_images.py` rewrites `web/images.json` from the icon files, and with
  `--badge` it turns a round logo into `web/ekasi.json`.
- `vercel.json` at the top of the repository tells Vercel to build `web/` and serve `web/dist`.
  Any static host works the same way with the built file.

Files from the website were checked with `verify.py` the same way as the command-line ones:
closed solids, no overlaps, and a code that matches module for module.

## Colourways

`python lnkey.py --list-colorways` lists them: `classic` (white / black / orange), `ekasi`, `bitcoin`
(orange body), `midnight` (black body, white QR field), `ohio`, `cafe`, `forest`, `ocean`,
`sunny`, `mono`. Add your own in the `COLORWAYS` table at the top of `lnkey.py`: body, field
(the light colour behind the code), ink (the dark modules) and accent (the back icon).
The code needs a light field and a dark ink. Black, navy, brown or dark green on white, cream,
yellow or orange all read well.

## Orders in bulk

Fill in `orders_example.csv` (one row per order, `qty` for repeats) and run

```
python lnkey.py --batch orders.csv -o out/friday
```

You get one `.3mf` per order in `out/friday/single/` and ready-to-print plates
(`plate_flush_white-black-orange_1.3mf` …). Orders that print the same way and need four
filaments or fewer between them are packed onto the same plate.

## In Bambu Studio

1. **Open the `.3mf`** (File → Open Project, or drag it in). Studio may note that it is loading
   geometry only. That is expected: the file carries shapes and filament numbers, not printer
   settings. Pick the A1 and your usual 0.20 mm profile.
2. **Filaments.** Each part is already assigned to filament 1, 2, 3 … in the order printed by the
   generator (`filaments: slot 1 white, slot 2 black, slot 3 orange`). Load the AMS lite to match,
   or change the colours in the filament list. To recolour one feature, open the object in the
   Objects list and change that part's filament.
3. **Do not rotate or flip the model.** The retail edition is designed QR-down and its code is
   already mirrored so that it reads correctly from the plate side.
4. **Settings that matter**
   - 0.4 mm nozzle, 0.20 mm layers (the colour layers are built on a 0.2 mm grid; other layer
     heights give ragged colour boundaries).
   - Retail: the plate surface becomes the QR face. Textured PEI gives a matte, glare-free code;
     the smooth plate gives a glossy one. Clean the plate first.
   - Slow the first layer a little (30 mm/s) for crisp modules.
   - Print solid: 5 walls, 100% infill. A sparse core weakens the loop and shows through light
     plastic as a shadow pattern behind the code.
   - Keep the prime tower on. Leave "flush into infill" off, because these parts are solid.
   - Do not iron: on a multi-colour top face it drags dark plastic across light.
5. **Arrange** if you want Studio to repack the plate, then slice. The slice summary gives the
   real time, grams and number of filament changes. Use those numbers in the pricing sheet.

### NFC (`--nfc`)

The generator leaves a 26 mm × 0.6 mm pocket in the middle of the tag and tells you the layer
(`add a pause before layer 10`). In the preview slider, right-click that layer → Add Pause. When
the printer stops, press a 25 mm NTAG213/215 sticker into the pocket and resume. Write the tag
first with any NFC app: a URI record containing `lightning:you@wallet.com`.

## What the QR says

| `--payload` | text in the code | notes |
|---|---|---|
| `uri` (default) | `lightning:name@domain` | Smallest code that a phone camera hands straight to a wallet app. |
| `plain` | `name@domain` | A phone camera treats it as an e-mail address. |
| `lnurl` | `LIGHTNING:LNURL1…` | Classic LNURL-pay. The code is denser, so the tag grows (58 mm for this address). |
| `raw` | anything you pass | Websites, nostr profiles, a shop page. |

The generator picks the smallest QR version that fits and then the strongest error correction
that still fits in it (for `jasonbohio@blink.sv`: version 3, 29 × 29 modules, level Q, so a quarter
of the code can be damaged and it still reads).

`--invert` gives light modules on a dark field. It looks sharp, but some wallet scanners do not
read inverted codes, so test before selling one.

## verify.py

Reads the `.3mf` back from disk and checks that every part is a closed solid, that no parts
overlap, and that the QR face decodes to the expected text. The face is sliced from the real meshes
and pictured the way a phone sees it, then read with two independent decoders and compared module
by module, the right way round.
Run it on anything you are about to print in quantity.

## Print check (optional)

`tools/slice_check.py` slices a tag with PrusaSlicer set up like the A1's 0.20 mm profile, reads
the G-code back and paints every extrusion line in its filament colour, so you see the printed
faces rather than the model. It decodes the QR from those painted toolpaths, measures how much
of each colour really gets laid down, and reports filament changes and the time estimate.

```
python tools/slice_check.py jasonbohio@blink.sv --edition retail --back trombone
```

It needs `prusa-slicer` on the PATH. `samples/print-check-toolpaths.png` shows the result for
one tag of each edition (plate side, then top).
What it settled for these designs:

- Dark QR modules are drawn at exactly their nominal size on the plate side (pulled in, they
  printed 11% too small) and 0.02 mm under on raised codes. On the stock A1-style profile the
  painted code matches the ideal code on 97-98% of its area.
- Narrower line widths and a 0.2 mm nozzle were tried (`PROFILES` in the script). Neither made
  the code measurably truer, and the fine nozzle took 3.5 times as long, so the stock 0.4 mm
  profile is the one to use.
- Pictures replaced lettering altogether: big filled shapes print cleanly where 2-3 mm letters
  were the weakest part of the earlier tags.

## Edges

The three outermost layers on each face step in by 0.45, 0.25 and 0.10 mm, which gives the tag
a 45-degree bevelled edge front and back, round the key-ring hole too. It feels finished in the
hand, hides first-layer squish, and needs no supports.

## Limits

- These files were checked geometrically and by decoding, and the project format follows Bambu
  Studio's own import code, but they have not been opened in Bambu Studio or printed yet. Print
  one of each edition and scan it with several wallets before taking orders. If the filament
  numbers do not come through, the per-colour STLs (`--stl`) are the fallback: import them
  together as one object with multiple parts.
- The print check uses PrusaSlicer, a close relative of Bambu Studio's slicer, not Bambu Studio
  itself, and a toolpath picture is not a print: it cannot show stringing, colour bleed or
  first-layer squish.
- Grams are computed from the solids at 1.24 g/cm³. PrusaSlicer's estimate for a full plate of
  19 is roughly 5 hours (meetup), 6.5 hours (Ekasi) and 7 to 8 hours (retail) before filament-change
  time; trust Bambu Studio's own figure.
- Short addresses make smaller codes (and smaller tags); long ones make bigger ones. Keep
  `--module` at 0.9 mm or more with a 0.4 mm nozzle.

## Licences

- Icons: Material Design Icons by Pictogrammers, Apache 2.0 (`icons/LICENSE-MDI.txt`).
  The trombone, food truck, orange pill, sats, zap coin, tip jar and home miner were drawn for
  this kit (`tools/make_custom_icons.py`); the bitcoin coin is the Material Design bitcoin icon at
  full size. The Bitcoin mark itself is public domain.
- Fonts in `fonts/` (used only for preview labels and the placeholder logo): Inter and
  Liberation Sans Narrow, both SIL Open Font License.
- The website loads three.js (MIT) from cdnjs and the Anton and DM Sans typefaces (SIL Open Font
  License) from Google Fonts, and bundles qrcode-generator (MIT) and earcut (ISC).
- Bitcoin Ekasi's logo (`logos/bitcoin-ekasi/`, `web/ekasi.json`) belongs to Bitcoin Ekasi and is
  used with their permission.
- Do not put a company's logo on a tag unless that company asked you to.
