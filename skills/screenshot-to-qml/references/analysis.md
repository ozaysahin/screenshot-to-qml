# Measuring a screenshot

Numbers come from pixels, not from impressions. Look at the image to decide *what* things
are (a button, a repeated row, a chart); run `scripts/probe.py` to learn *how big, where and
which color* they are.

## Contents
- Automatic draft (analyze.py)
- Matchers: fonts, icons, shadows, gradients (match.py)
- Design size and DPR
- Measuring workflow
- Colors (solid, alpha, gradients, shadows)
- Geometry (boxes, padding, gaps, radius, borders)
- Text (strings, sizes, weights, line boxes)
- Icons and images
- Several screenshots of one screen (states, themes)
- Input quality problems

## Automatic draft (analyze.py)

`analyze.py input.png --dpr D --out-dir analysis` runs three analyzers and merges them into
`design-spec.draft.json` plus `overlay.png`:

| Analyzer | Finds | How | Accuracy on the eval set |
| --- | --- | --- | --- |
| `palette.py` | solid colors (fills, borders, text stems, icon strokes) | pixels equal to both neighbours on one axis, counted, merged at ΔE ≤ 1.2 | 95 % of solid design colors within ΔE 2 |
| `geometry.py` | surfaces: box, fill, radius, border, parent, repeat groups | connected regions per fill color (4- and 8-connected), filled outline ≥ 75 % of the box | 94 % of solid surfaces outside dense grids (a 168-cell heatmap is mostly missed), box error mostly < 0.6 px |
| `text_ocr.py` | text runs: string, ink box, font px, color; icon candidates | tesseract (tur+eng) in three passes, runs re-read as single lines | 73 % strings exact (CER 13 %), font px ±1.4 |

What the draft does not know, and you must add: token names by role, surface roles,
translucent surfaces (glass, tinted chips), states, models (it only hints repeats in
`hints.repeats`). Font families and weights, icon identities, shadows and gradients come from
`match.py` (next section) once the surfaces, text runs and icon boxes are right.

OCR failure patterns to check first (entries with `verify: true`): Turkish ı/i and İ/I, `·`
read as `-` or `.`, `%` and `₺` misread or dropped, monospace `0` read as `6`/`8`, lost spaces
in tightly spaced fonts, icon-font glyphs read as `©` `@` `&` (those become icon candidates).
Very small (≤ 12 px) dim text is often missed entirely — find it on the overlay.

## Matchers: fonts, icons, shadows, gradients (match.py)

Run after correcting the draft (boxes and strings must be right: the matchers measure inside
them):

```bash
python <skill>/scripts/match.py input.png design-spec.json --out design-spec.json --fonts-dir analysis/fonts
# -> fonts, weights, icon matches, style.shadow, style.fillImage written into the spec (src "measured")
# -> design-spec.match-report.json: every value with its score, alternatives and "check" notes
```

| Matcher | Finds | How | Accuracy |
| --- | --- | --- | --- |
| `font_match.py` | family, weight, px per text run; the screen's 1–3 families | each run rendered in 63 open UI families at their weights (FreeType, variable axes like CSS), compared by shape, width and ink mass; runs vote for the screen's families | family 95 % of runs, weight ±100 96 %; 17 hold-out families: 95 % of runs, 16/17 screens |
| `icon_match.py` | `set:name` + stroke width per icon box | 11,869 icons of 8 sets indexed at 32×32; best 40 re-rendered at the box size (stroke sets at 7 widths, 1.25–2.75); the screen's dominant sets get a bonus | top-1 90 %, top-3 94 % |
| `shadow_fit.py` | CSS `box-shadow` (x, y, blur, spread, color) per surface | Gaussian-blurred box + smooth background fitted to the ring around the box; neighbours' shadows subtracted (scene mode) | found on 31 of 44 shadowed surfaces (27 of 31 outside the glass case), no false alarm on 78 others; blur 1.8 px, y 0.25 px median error; synthetic cards: blur 1.1 px, y 0.1 px |
| `gradient_fit.py` | CSS `linear-gradient` (angle, 2–4 stops) per surface | direction of steepest change, piecewise-linear color along the CSS gradient line, consensus fit that ignores undeclared content | angle 0.7°, end-stop ΔE 0.9 (8 eval gradients); synthetic: 0.04°, ΔE 0.15, stop count 96 %; 0 of 49 solid surfaces called gradients |

What still needs your eyes (the report lists these under `check`):

- Fonts: proprietary faces are not in the catalog; the closest open family comes back (SF Pro
  → Inter, Segoe UI → Open Sans/Noto Sans). Say "substitute" in the README. When the runs
  disagree the report sets `fonts.outsideCatalog` (typography.md has the fitting steps). Short runs (1–2
  characters) and icon-font glyphs get the screen's family, not their own measurement.
- Icons: below score 0.6 nothing is written (a custom glyph or a set that is not indexed:
  Material Symbols and Phosphor are not); pick from the candidates, draw it, or ask. Scores
  0.6–0.9 are written but listed: most wrong matches on the eval set scored there.
- Shadows: subtle shadows (alpha ≤ 0.06), shadows on dark or busy backgrounds (glass over
  blurred blobs) and cards packed closer than their blur are the weak spots. `atBound` or
  `hasShadow: false` on a surface that visibly has one means: measure by hand (below).
  Multi-layer shadows come back as one equivalent layer.
- Gradients: translucent (glass) surfaces over a colorful backdrop read as gradients. That is
  a fair static stand-in, but keep the real structure (translucent fill + backdrop) when the
  profile allows blur.

Caches (once per machine, network): `python <skill>/scripts/font_match.py fetch` (≈40 MB,
google/fonts) and `python <skill>/scripts/icon_match.py fetch` (≈170 MB, npm). Without them
match.py skips fonts/icons and exits 1; shadows and gradients need nothing.

## Design size and DPR

Everything in the spec and the QML is in **design px** (CSS px / QML logical px).

`design size = screenshot size / DPR`

| Screenshot | Typical DPR | Design size |
| --- | --- | --- |
| 2880×1800, 2560×1600 (Mac Retina) | 2 | 1440×900, 1280×800 |
| 1800×1125 (Windows at 125%) | 1.25 | 1440×900 |
| 1170×2532 (iPhone) | 3 | 390×844 |
| 1920×1080 kiosk capture | 1 | 1920×1080 |

When unsure, check a thin line: a 1 design-px border is 2 device px wide at DPR 2. If the user
knows the target device, ask. Pass `--dpr` to every probe command.

## Measuring workflow

Measure only what the draft lacks or flags, and batch it: each call costs a round trip, so
one call with ten boxes beats ten calls.

1. `region X Y W H [X Y W H ...]`: fills (largest cluster) and text/icon colors (small
   clusters) of every box you need, in one call.
2. `edges X Y W H [X Y W H ...]`: runs of constant color along each box's center row and
   column; element edges, border widths, padding and gaps come straight out of the run
   lengths.
3. `color X Y [X Y ...]` for exact colors of small things (dots, lines, badges).
4. `crop X Y W H --zoom 4` only for a detail the overlay cannot show (a corner radius, an
   icon's stroke), not once per region. `ruler` only when the overlay gives no positions.
5. Record everything in `design-spec.json` (see design-spec.md) while you measure.

## Colors

- Sample **flat interior** pixels, never edges (antialiasing) or text.
- Round to the nearest value only when two samples of the same element differ by ≤ 2 per channel.
- Translucent surfaces (tinted chips, badges, glass): the screenshot shows the composite. Find
  the underlying tint by sampling the same element over two different backgrounds, or assume a
  common alpha (0.08, 0.12, 0.14, 0.16, 0.24) of the accent color and check:
  `composite = alpha * tint + (1 - alpha) * background`. Mark as `inferred`.
- Gradients: `gradient_fit.py IMG --box X Y W H [--radius R] [--mask X Y W H]` measures one
  box. By hand: sample 3–5 points along the suspected axis; linear change in RGB means two
  stops; equal colors lie on lines perpendicular to the gradient direction.
- Shadows: `shadow_fit.py IMG --box X Y W H [--radius R]` measures one box (`--spec` fits the
  whole screen). By hand: sample outward from the edge until the background returns; the
  distance is roughly `blur + spread + |offset|`; the darkest step next to the edge gives the
  color × alpha. Mark hand-measured shadows `inferred` with conf ≤ 0.7.

## Geometry

- Box edges: `edges` runs. A 1 px run of a different color at the boundary is a border.
- Padding = first content edge − box edge. Gaps = distance between sibling boxes.
- Radius: crop a corner at zoom 8; count the pixels from the corner to where the edge becomes
  straight on each axis.
- Repeated items: measure one, then confirm the pitch (item + gap) across all of them. Record
  `model` with the count instead of every item's box.
- Snap values to the design's scale only when the measurements support it (4/8 px grids are
  common but not universal).

## Text

- Strings: read them verbatim, including punctuation, thousands separators (1.248 vs 1,248),
  decimal commas (%87,4), Turkish letters (ı İ ş ğ ç ö ü) and case. Uppercase labels are
  uppercase in the spec.
- Size: cap height from a zoomed crop. UI sans fonts have cap heights of 0.69–0.75 × font px
  (Inter 0.728, Manrope 0.720, Barlow 0.700, Outfit 0.694, Plus Jakarta Sans 0.745), so
  `px ≈ cap height / 0.72`, rounded to an integer; refine once the family is known.
- Weight: compare stem thickness with other text in the same image; UI designs usually use
  400/500/600/700.
- Line box: the vertical distance between baselines of wrapped lines, or the height of the
  element that contains a single line.
- Family: `font_match.py` (via match.py); check the verdict on distinctive glyphs
  (typography.md).

## Icons and images

- Record the box and color of each icon; `icon_match.py` (via match.py) fills `match` like
  `lucide:gauge`, the score and the stroke width. Check low scores by eye (icons-vectors.md).
- Photos and illustrations are content: crop them from the screenshot only when the user
  confirms they may ship; otherwise use a placeholder of the same size and say so.

## Several screenshots of one screen

Hover/pressed/disabled/dark variants: measure each, then store the differences as `states`
in the spec (e.g. `button.hover.fill`). Values that only exist in one variant are `measured`;
values you invent for missing states are `assumed`.

## Input quality problems

- JPEG: colors shift and edges ring. Sample larger flat areas; lower confidence; ask for PNG.
- Scaled screenshots (not an integer DPR, blurry text): measure in design px anyway; expect
  ±1 px uncertainty and say so in the report.
- Cropped screenshots: ask for the full screen size, or treat the visible area as the canvas.
