# Layout

## Contents
- Canvas or responsive
- Choosing the positioning tool
- CSS flex → Qt Quick Layouts
- Gotchas that cost pixels
- Text line boxes

## Canvas or responsive

| Screen | Main.qml | Why |
| --- | --- | --- |
| Kiosk, HMI, panel with a known resolution | `Main.canvas` template: fixed `Theme.designWidth × designHeight` stage, `scale: fitScale` | Pixel-exact on the target; letterboxes elsewhere |
| Desktop app, resizable window | `Main.responsive` template: Layouts fill the window | Reflows instead of scaling |
| Mobile screen | responsive, design width as the reference | Heights scroll, widths reflow |

Inside a canvas, still use Layouts — the canvas only fixes the outer size. Absolute `x`/`y` for
whole screens is fidelity-mode only.

## Choosing the positioning tool

1. Items that flow in a row/column and may stretch → `RowLayout` / `ColumnLayout` / `GridLayout`.
2. Rows that must wrap onto new lines → `FlexboxLayout` (Qt 6.10+, tech preview; yoga-based, a
   subset of CSS flexbox, no `space-evenly` in 6.10). Below 6.10: `Flow`.
3. Overlays, badges on corners, centered content, items pinned to an edge → `anchors`.
4. Fixed children with no stretching → `Row` / `Column` (cheaper than Layouts).
5. Scrolling content → `ListView` / `GridView` / `Flickable` (with `clip: true`).
6. Absolute `x`/`y` → computed positions (charts, gauges), never as a layout shortcut.

## CSS flex → Qt Quick Layouts

| CSS | QML |
| --- | --- |
| `display:flex; flex-direction:row; gap:G` | `RowLayout { spacing: G }` |
| `flex-direction:column` | `ColumnLayout` |
| `flex: 1` on one child | `Layout.fillWidth: true` (fillHeight in a column) |
| `flex: 1` on N siblings (equal columns) | see gotcha 2 |
| `justify-content: space-between` | `Item { Layout.fillWidth: true }` spacers between children |
| `justify-content: center` / `flex-end` | spacers on both sides / a leading spacer |
| `align-items: center` | `Layout.alignment: Qt.AlignVCenter` (row) / `Qt.AlignHCenter` (column) |
| `align-items: baseline` | `Layout.alignment: Qt.AlignBaseline` on each Text |
| `margin-left: auto` | a spacer before the item |
| `padding` | `anchors.margins` on the inner layout, or `Layout.margins` |
| `grid-template-columns: 520px 1fr 520px` | `RowLayout` with `preferredWidth: 520; fillWidth: false`, a `fillWidth` middle |
| `grid-template-columns: repeat(N, 1fr)` | `GridLayout { columns: N }`, children `fillWidth` + equal preferredWidth |
| `position:absolute; top; right` | `anchors.top/right` + margins inside the parent |
| `overflow:hidden` | `clip: true` (rectangular only — see effects.md for rounded clipping) |
| `z-index` | `z` |

## Gotchas that cost pixels

1. **Nested layouts inherit `fillWidth`.** A `ColumnLayout` whose child fills becomes a filler
   itself. A fixed-width column needs `Layout.fillWidth: false` explicitly, or it steals width
   from the real filler.
2. **Equal columns.** CSS `flex: 1 1 0` ignores content width; Qt Layouts start from implicit
   sizes, so columns drift by a few px when contents differ. For exact equality set
   `Layout.preferredWidth: (row.width - (n - 1) * row.spacing) / n` and no fillWidth.
3. **`space-between` with text.** Put `Item { Layout.fillWidth: true }` between labels, or a
   `Row` whose spacing is `(width - sum of label widths) / (n - 1)`. Centering each label in an
   equal cell is *not* the same thing.
4. **Borders are inside the box in QML.** `Rectangle.border` is drawn inside the width/height,
   like CSS `box-sizing: border-box`. Content offset = border + padding.
5. **Rounded corners do not clip children.** Clip with an inner shape (see effects.md) or give
   the child matching per-corner radii (`topLeftRadius` … Qt 6.7+).
6. **Pixel snapping.** Layout positions are rounded to whole px; CSS keeps fractions. A 36 px
   chip centered in 75 px sits at 19.5 in CSS and 20 in QML. Accept ≤ 1 px.
7. **Signal-handler names.** A property called `onSomething` is parsed as a handler. Never name
   tokens `onAccent`, `onPrimary` — use `accentInk`, `primaryInk`.

## Text line boxes

CSS centers the font's ascent+descent box inside the line box. Reproduce single-line labels with
`height: <line-height>; verticalAlignment: Text.AlignVCenter` — this puts glyphs where the
browser put them without guessing baseline offsets. For mixed sizes on one baseline (value +
unit), place the second Text with `y: first.y + first.baselineOffset - baselineOffset`, or use
`Layout.alignment: Qt.AlignBaseline`. Multi-line paragraphs: `lineHeight` with
`lineHeightMode: Text.FixedHeight` and `wrapMode: Text.WordWrap`.
