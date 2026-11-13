**English** | [繁體中文](README.md)

# Word Viewer

A `.docx` viewer built with PySide6 + QtWebEngine + [docx-preview](https://github.com/VolodymyrBaydalka/docxjs). Page size, fonts and layout stay as close to Word as possible. It supports zoom, page navigation, PDF export and printing.

## Install and run

### Requirements

- **OS**: Windows 10 / 11 (64-bit). Only tested on Windows 11.
- **[uv](https://docs.astral.sh/uv/)**: creates the environment and installs packages.
- **Python 3.12 or later**: `uv sync` downloads it automatically according to `.python-version`; no separate install needed.
- **Python packages**: `uv sync` installs PySide6 (bundles QtWebEngine and Chromium) and fonttools. No separate browser or Qt install is needed; PySide6 is large, so the first install takes a while.
- **Not required**: Word / Office / LibreOffice, a network connection (docx-preview and JSZip are bundled), GPU acceleration.

Optional items that affect appearance:

- **PMingLiU (新細明體) and Times New Roman**: built into Traditional Chinese Windows. Without them, fallback fonts are used and the layout differs more from Word.
- **Cloud fonts (e.g. Aptos)**: if a document uses them, they must already be downloaded on this machine (opening Word downloads them); otherwise Latin text falls back to another font. Windows only.
- **Printer driver**: only needed for printing; PDF export does not need one.

macOS / Linux are untested: PySide6 supports both so the program should run, but the fonts above are usually missing and the layout differs more. Linux also needs system graphics libraries (e.g. xcb-related packages).

### Run

```
uv sync
uv run python -m wordview [file.docx]
```

## Usage

| Feature | How |
|---|---|
| Open | Toolbar "Open", Ctrl+O, or drag a `.docx` into the window (the dialog starts in the current document's folder) |
| Export PDF / Print | Toolbar buttons, Ctrl+E / Ctrl+P (page size follows the source file) |
| Navigate | Previous/next in the status bar, PageUp / PageDown, or type a page number and press Enter |
| Zoom | Zoom out/in/ratio dropdown in the status bar, Ctrl+wheel, Ctrl+- / Ctrl+=; fit width, fit page; Ctrl+0 resets to 100% |

## Matching Word's layout

docx-preview approximates Word with HTML. This project adds the following after rendering (`src/wordview/assets/viewer.js`):

- **Line grid (docGrid)**: with `type="lines"`, Word snaps every line height to a multiple of `linePitch`. Line heights are adjusted accordingly, and empty paragraphs take a full line.
- **Pagination**: content is paginated by page height, and paragraphs may split between lines, giving the same total page count as Word.
- **Fonts**: Latin and East Asian fonts are resolved in the order Normal style → theme fonts → docDefaults. Styles that only specify an East Asian font get the Normal style's Latin font for Latin text.
- **Cloud fonts**: Windows cloud fonts (e.g. Aptos) are invisible to the embedded browser. `fonts.py` turns the fonts a document uses into `@font-face` rules (only those already downloaded on this machine).
- **CJK/Latin spacing**: `text-autospace` is applied, and adjacent full-width punctuation is squeezed like Word's "compress punctuation".
- **Paragraph borders**: left borders of type `doubleWave` and `dashed` keep their distance from the text and join across adjacent paragraphs; paragraph left/right borders are not drawn inside table cells.
- **Image paragraphs**: extra space below images, underlines on image runs (e.g. dotted) drawn under the picture; symbols such as `●□★` use the East Asian font.

## Project structure

```
src/wordview/
├─ __main__.py      entry point
├─ main_window.py   main window: icon toolbar, status bar (pages / zoom), printing and PDF export
├─ icons.py         vector icons (SVG → QIcon) and the app icon
├─ fonts.py         cloud fonts → @font-face
└─ assets/
   ├─ viewer.html / viewer.js   rendering, layout fixes, zoom, page numbers
   ├─ icon.svg                  app icon
   ├─ docx-preview.min.js       docx-preview 0.3.3 (Apache-2.0)
   └─ jszip.min.js              JSZip 3.10.1 (MIT or GPL-3.0)
tests/test_smoke.py  builds A4 / Letter files → exports PDF → checks page count and paper size
```

## Tests

```
uv run pytest
```

## Known limitations

- HTML only approximates Word. Complex objects (text boxes, SmartArt, some field codes) may differ, and glyph rasterization differs from Word, so stroke weight looks slightly different.
- The CJK/Latin auto-spacing width differs from Word (about 1/8 em in the browser vs. about 1/4 em in Word), so some lines wrap differently.
- Pagination is an approximation; individual page breaks may differ slightly from Word.
- `.docx` only; legacy `.doc` is not supported. Windows is the primary tested platform.
