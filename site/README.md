# Hosted browser run (GitHub Pages)

`site/` is a static page that runs the original Windows 3.1 `WINMINE.EXE` on
Windows 3.0 through the WM88 bridge, in the visitor's browser (emulated 80286,
not an 8088 proof).

**This directory contains no Microsoft software and no ROM images.** On click,
the visitor's browser fetches pinned public reference media, verifies every
SHA-256 (see `app.js`), cuts `WINMINE.EXE` out of the Windows 3.1 image
(must be exactly 27,776 bytes, SHA-256 `633c1328...e15e80b`), builds the guest
disk in memory with `compose.js`, and passes it to PCjs through
`window.resources`. Nothing is uploaded or stored.

- `pcjs_media.js` / `compose.js`: JavaScript port of `tools/pcjs_media.py` and `compose()` in `tools/prepare_pcjs.py`.
- `ours/`: this project's own files only (bridge, shim, tests, boot scripts).
- `vendor/`: PCjs runtime, MIT, pinned to commit `9e5409ab`.

Parity test (the JS composer must equal the Python builder byte for byte):

```sh
python3 tools/prepare_pcjs.py --reference-media --out ../86to88-private-judge
node site/test/parity.mjs <PCDOS320-WIN300-EGA.json> <PCDOS330-WIN310-VGA.json> ../86to88-private-judge/disk.json
```

Local preview: `python3 -m http.server 8080 --directory site`, then open <http://127.0.0.1:8080/>.
