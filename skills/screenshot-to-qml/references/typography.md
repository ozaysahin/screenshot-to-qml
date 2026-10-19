# Typography

## Contents
- Identify the family
- Get and bundle the font
- Use it from QML
- Size, weight, spacing, line height
- Casing and Turkish text
- Metrics differences (browser vs Qt)

## Identify the family

Measure first, then confirm by eye:

```bash
python <skill>/scripts/font_match.py fetch                                  # once: 63 open UI families (~40 MB)
python <skill>/scripts/font_match.py match input.png --spec design-spec.json [--out fonts.json]
# or as part of match.py, which also writes the result into the spec
```

`font_match.py` renders every run of the spec in each candidate family at its weights
(variable axes set like CSS, `opsz` = px), scales it to the run's ink height and scores shape,
width and ink mass. Runs vote for the screen's families (a sans, plus a monospace family when
numeric runs want one). On the eval set it names the right family for 95 % of the runs;
on 17 families it was not tuned on, 95 % of runs and 16 of 17 screens. Weight is within ±100 on 96 %
of runs; the
exact weight is harder (400 vs 500 differ by a few percent of ink), so check headings and
buttons by eye.

Then confirm on distinctive glyphs at zoom 4–8, especially when the top two families score
within 0.02 (see `alternatives` in the output):

| Look at | Tells apart |
| --- | --- |
| `G` spur, `R` leg, `a` single/double storey, `t` top | Inter vs Roboto vs SF-like grotesques |
| geometric round `o`, `e` with horizontal bar, circular dots | Manrope, Outfit, DM Sans, Nunito (rounded terminals) |
| square-ish rounds, narrow width | Barlow, Rajdhani, Oswald (HMI/industrial) |
| slashed/dotted `0`, uniform advance | monospace: JetBrains Mono, IBM Plex Mono, Roboto Mono |
| `1` flag and `4` shape in numerals | numeric-heavy UIs; confirm with digits |

Screens often mix a sans for labels with a mono for values. Check every numeric run on its own:
measure its width with `probe.py edges` and divide by the character count. About 0.6 × the font
size per character, including `%` and `.`, means monospace, even when bold digits look like the
sans. In the baseline eval, both arms missed a bold JetBrains Mono `72%` this way.

Record the result in the spec (match.py does it). If the design system is known (Material →
Roboto, Fluent → Segoe UI, Apple → SF Pro), prefer its font or its open substitute and say so:
proprietary faces are not in the catalog, so font_match returns the nearest open family.

## Get and bundle the font

- Open fonts (Google Fonts / OFL: Inter, Roboto, Manrope, DM Sans, Nunito, Outfit, Barlow,
  JetBrains Mono, Plus Jakarta Sans, Space Grotesk, …) are redistributable: bundle them in
  `assets/fonts/`. Source: `https://raw.githubusercontent.com/google/fonts/main/ofl/<family>/`.
- Prefer static TTFs per weight. `match.py … --fonts-dir analysis/fonts` writes them for the
  weights the screen uses (variable fonts instanced with fontTools, named so Qt selects them by
  family + weight) plus the license file; pass them to `scaffold.py --fonts analysis/fonts/*`.
  A family whose OFL declares a Reserved Font Name is copied unmodified instead (a modified
  font must not keep a reserved name); Qt then selects weights on the variable font itself.
- Proprietary faces (SF Pro, Segoe UI, Helvetica Neue, paid foundry fonts): do not bundle.
  Substitute (SF Pro → Inter, Segoe UI → Inter/Open Sans, Helvetica → Inter/Arimo) and list the
  swap in the README; the user can drop licensed files into `assets/fonts/`.
- **Font outside the catalog** (`outsideCatalog: true` in the match report: on the median run
  another family fits better than the voted one by > 0.08, so no candidate is the face; it
  catches about 6 in 10 outside faces, the rest have a near twin in the catalog):
  1. Ask for the font name or file if the user is there. An open family is fetched and
     confirmed by name: `font_match.py fetch --families "Name"`, `font_match.py match input.png
     --spec design-spec.json --families "Name"` (scores should rise), then
     `font_match.py bundle "Name" --weights 400,600 --out analysis/fonts`.
  2. Otherwise keep the voted family as the substitute and fit each text token's
     `pixelSize` (and `letterSpacing` for long uppercase labels) so rendered widths match the
     screenshot within ~2 %: measure with `probe.py edges`, compare with the render. Keep the
     baselines; let alignment carry centered and right-aligned text.
  3. README: "font not identified; substitute X, sizes fitted to the screenshot".
- Icon fonts (Font Awesome Free, Material Symbols, Lucide, Tabler webfont) are fonts too: bundle
  the TTF and address glyphs by code point (icons-vectors.md).

## Use it from QML

- `main.py` loads every file in `assets/fonts/` and logs the families Qt reports. Use exactly
  those names in the Theme (`Font Awesome 7 Free`, not the file name).
- Define font tokens once: `readonly property font title: Qt.font({family: fontSans, pixelSize: 22, weight: Font.DemiBold})`
  and use `font: Theme.title`.
- Always `pixelSize`, never `pointSize`.
- Weights: 100 Thin · 200 ExtraLight · 300 Light · 400 Normal · 500 Medium · 600 DemiBold ·
  700 Bold · 800 ExtraBold · 900 Black. 600 is `Font.DemiBold`, not Bold.

## Size, weight, spacing, line height

- CSS `letter-spacing: 1px` → `letterSpacing: 1` in the font token (absolute px).
- `line-height` → see layout.md "Text line boxes": fixed-height Text with `AlignVCenter` for
  single lines; `lineHeight` + `Text.FixedHeight` for paragraphs.
- `text-overflow: ellipsis` → `elide: Text.ElideRight` with a width.
- Tabular numbers (`font-variant-numeric: tabular-nums`): monospace fonts are already tabular;
  for proportional fonts use a monospaced-digit family or fixed-width value boxes.

## Casing and Turkish text

- Write uppercase labels in uppercase in the source (`"ACİL DURDUR"`, `"NOVA MAKİNE"`).
  `font.capitalization: Font.AllUppercase` is not locale-aware and turns `i` into `I`, not `İ`.
- Keep ı/İ/i/I distinct everywhere (search, sorting, uppercase helpers).
- Check glyph coverage: every bundled font must contain ç ğ ı İ ö ş ü Ç Ğ Ö Ş Ü (and ₺ when used).
  `fontTools`: `all(ord(c) in TTFont(f).getBestCmap() for c in "çğıİöşüÇĞÖŞÜ₺")`.
- Numbers for Turkish UIs: decimal comma, dot thousands (`1.248`, `%87,4`);
  `Number(v).toLocaleString(Qt.locale("tr_TR"), "f", 1)`.

## Metrics differences (browser vs Qt)

- Qt Quick's default text renderer uses fractional glyph advances, like Chrome on macOS/Windows.
  Headless Chrome on Linux rounds advances to whole pixels unless started with
  `--font-render-hinting=none`; long strings then differ by ~0.4 px per character. Know which
  one produced the screenshot before chasing text widths.
- Line boxes: Qt's text box height is ascent + descent of the font (hhea/typo metrics) — the same
  box the browser centers inside the line height. Matching `height` + `AlignVCenter` lands within
  1 px.
- Small text on low-DPI embedded screens: `renderType: Text.NativeRendering` gives hinted,
  crisper glyphs at the cost of scaling quality. Do not use it on a scaled canvas.
