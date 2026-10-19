# Icons and vector graphics

## Contents
- Identify the icon set
- Three ways to draw icons (and when)
- Recolorable SVG icons via svgtoqml
- Illustrations, logos, charts
- Raster images

## Identify the icon set

```bash
python <skill>/scripts/icon_match.py fetch                        # once: 8 sets, ~11,900 icons (npm, ~170 MB)
python <skill>/scripts/icon_match.py match input.png --spec design-spec.json   # or via match.py
python <skill>/scripts/icon_match.py export lucide:gauge --stroke 1.75 --color "#1E293B" --out assets/icons
```

`icon_match.py` compares each icon box with Lucide, Tabler (outline, filled), Font Awesome
(solid, regular, brands) and Heroicons (outline, solid): a coarse pass over a 32×32 index, then
the best 40 re-rendered at the box size and, for stroke sets, at stroke widths 1.25–2.75. The
screen's dominant sets win ties. On the eval set the first answer is right for 90 % of the
icons (94 % within the top three). It returns the stroke width too: Lucide/Tabler drawn at 1.5 or 1.75 instead of 2 is
common and visible. `export` writes the SVG with that stroke and color for svgtoqml or
`VectorImage`; for an icon font, use the glyph with the same name.

Sets it does not index (Material Symbols, Phosphor, custom glyphs) come back with a low score
(< 0.6: nothing written). Identify those by style:

| Style in the screenshot | Likely set | npm package (SVG + font) | License |
| --- | --- | --- | --- |
| 24 grid, 2 px round strokes, friendly geometry | Lucide | `lucide-static` (`icons/*.svg`, `font/lucide.ttf`) | ISC |
| 24 grid, 2 px strokes, slightly more detail; filled variants | Tabler | `@tabler/icons` (`icons/outline`, `icons/filled`), `@tabler/icons-webfont` | MIT |
| Solid, heavy glyphs, many brand logos | Font Awesome Free | `@fortawesome/fontawesome-free` (`webfonts/*.woff2`, `svgs/`) | fonts OFL, icons CC BY 4.0 |
| Rounded/sharp/outlined, variable weight | Material Symbols | `material-symbols` (variable font) | Apache 2.0 |
| Thin/regular/bold/duotone families | Phosphor | `@phosphor-icons/core` | MIT |

Compare 2–3 distinctive icons (gear, bell, chevron) at zoom 8 with candidates. Record
`match: "set:name"` with the score; below 0.9 (or when you picked by eye), say "closest match"
in the README.

Always use the real icon from the set. Do not redraw icons with Rectangles or hand-made paths.

## Three ways to draw icons

1. **Icon font glyph** (default when the set ships a font: Font Awesome, Lucide, Tabler webfont,
   Material Symbols). One `Text` with `font.family: Theme.fontIcon`, `text: Icons.gauge`
   (escaped code point, e.g. `""`), `color` bindable, crisp at any scale. Code points:
   FA `metadata/icons.yml` (`unicode`), Lucide `font/info.json` (`encodedCode`).
   Font Awesome Solid needs `font.weight: Font.Black` (900).
2. **SVG → QML component** (when there is no font, stroke widths differ from the font, or the
   icon must be exactly the SVG): convert with `svgtoqml` and bind the color (next section).
3. **`VectorImage { source: "icon.svg" }`** (Qt 6.8+) for multi-color SVGs you do not need to
   recolor. `Image { source: "x.svg"; sourceSize: Qt.size(w * Screen.devicePixelRatio, h * Screen.devicePixelRatio) }`
   is the fallback below Qt 6.8 (rasterized, so set sourceSize or it blurs).

## Recolorable SVG icons via svgtoqml

```bash
sed 's/currentColor/#000000/g' icons/gauge.svg > /tmp/gauge.svg
pyside6-svgtoqml --curve-renderer /tmp/gauge.svg qml/App/Icons/GaugeIcon.qml   # or: svgtoqml (C++ Qt)
```

Then in the generated file: add `property color color: "black"` to the root Item and replace
every `strokeColor: "#ff000000"` / `fillColor: "#ff000000"` with `__qt_toplevel.color` (keep
`"#00000000"` transparent fills). The root scales its content to `width`/`height`, so
`GaugeIcon { width: 20; height: 20; color: Theme.accent }` is a sharp, themed vector icon.
Register the icons in a module (`qml/App/Icons/qmldir`) if there are many.

## Illustrations, logos, charts

- Multi-color SVG illustrations and logos: `VectorImage` (desktop) or pre-converted
  `svgtoqml` output (faster load, no runtime parsing). Keep the original SVG in `assets/`.
- Charts: draw with `Shape`/`PathSvg` for static dashboards (see `LineChart.qml` in the
  example) or Qt Graphs (`import QtGraphs`, PySide6-Addons) when interaction, axes and live data
  matter. Qt Charts is legacy; do not start new code with it.
- Donuts/rings: `Shape` with `PathAngleArc` (`startAngle`, `sweepAngle`, `capStyle`).

## Raster images

Photos, avatars, product shots: `Image { fillMode: Image.PreserveAspectCrop; sourceSize: … × DPR }`,
rounded with a mask (effects.md). Content images from the screenshot may only be cropped and
shipped when the user confirms the rights; otherwise use a same-size placeholder and list it.
Never use the screenshot itself (or large crops of it) as a background — the quality gate fails
the project.
