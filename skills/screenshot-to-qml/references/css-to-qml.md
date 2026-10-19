# HTML / CSS / Tailwind input

When the user gives HTML instead of (or with) a screenshot, the source already contains the
exact values. Two ways to use it:

1. **Render it and extract (preferred).**

   ```bash
   python <skill>/scripts/html_to_spec.py page.html --size W H --dpr D --out-dir analysis [--lang tr-TR]
   ```

   Headless Chromium renders the page at the design size (`--font-render-hinting=none`, so
   text metrics match Qt) and reads computed styles from the live DOM:

   - `analysis/input.png`: the reference image; pass it to `check.py --source`.
   - `analysis/design-spec.json`, every value `src: "truth"`:
     - tokens from `:root` custom properties (also inside `@layer`/`@media`, so a Tailwind v4
       `@theme` works); oklch/lab colors are converted to sRGB hex.
     - nodes for painted boxes, controls (`button`, `input`, `select`, ARIA roles), landmarks,
       and repeated children (same tag + first class, ≥ 3) as models.
     - every text run with font, baseline and case transform.
     - form-field values and placeholders (`field: "input:placeholder"`).
   - `analysis/icons/iN.svg`: each inline SVG icon with `currentColor` resolved. Use it as is
     with `VectorImage` or `svgtoqml` (icons-vectors.md); no icon matching needed.
   - `analysis/fonts/`: the files behind the page's local `@font-face` rules. Pass them to
     `scaffold.py --fonts`. Families without `@font-face` are system fonts: find the file or
     substitute (typography.md).

   Node ids are `tag.class[n]`; rename the ones you build components from. The render is what
   Chromium draws at that size and DPR (pixel-identical to a screenshot from the same Chromium
   build), so the check loop scores against what the page really looks like.
2. **Read it.** For small snippets, translate declarations by hand with the table below.

Either way the output is the same Theme + components structure; HTML nesting is not copied 1:1.
Wrapper `div`s that only exist for CSS become layout properties, repeated markup becomes a model.

What the extraction cannot see, so look at `input.png` for it:

- `::before`/`::after` boxes (switch knobs, custom checkmarks, decorative dots) are not nodes.
- `:hover`/`:focus` rules only show when that state is on the page; read the CSS for the other
  states and map them to control states (controls.md).
- Gradient text (`background-clip: text`) is recorded on the text run as `fillImage`; build it
  with a gradient masked by the text (effects.md).
- Tailwind v4 gradients interpolate `in oklab`; Qt interpolates in sRGB, so add a middle stop
  with the oklab midpoint color when the two ends differ in hue.

## Translation table

| HTML / CSS / Tailwind | QML |
| --- | --- |
| `<div>` with background/border | `Rectangle` |
| `<div>` without paint | `Item` or a Layout |
| `display:flex` / `grid` | layout.md table |
| `gap: 20px` | `spacing: 20` (layouts) |
| `padding: 24px` | margins on the inner layout; remember the border (layout.md gotcha 4) |
| `background: #e8e8ec` | `color: Theme.surface` (token) |
| `border-radius: 44px` | `radius: 44`; per corner: `topLeftRadius` … (Qt 6.7+) |
| `border: 2px solid c` | `border.width: 2; border.color: c` (drawn inside the box) |
| `box-shadow` | effects.md (`MultiEffect` shadow on Qt 6.8, `RectangularShadow` from 6.9) |
| `linear-gradient(...)` | effects.md gradient table |
| `rgba(0,0,0,.28)` | `"#47000000"` — alpha FIRST in QML (`round(0.28 × 255) = 71 = 0x47`) |
| `#RRGGBBAA` (CSS) | reorder to `#AARRGGBB` |
| `opacity: .4` on a group | `opacity: 0.4` + `layer.enabled: true` (effects.md) |
| text | `Text { text; color; font: Theme.x }` |
| `font-weight: 600` | `Font.DemiBold` |
| `letter-spacing: -.2px` | `letterSpacing: -0.2` (in the font token) |
| `line-height: 24px` | layout.md "Text line boxes" |
| `text-transform: uppercase` | write the uppercase string (typography.md, Turkish İ) |
| `text-overflow: ellipsis` | `elide: Text.ElideRight` |
| `<img>` | `Image { sourceSize … }` |
| inline `<svg>` | icons-vectors.md (icon font, svgtoqml component, or VectorImage) |
| `:hover` / `:active` / `:disabled` / `:focus-visible` | control state bindings (controls.md) |
| `<button>`, `<input>`, `<select>`, `<input type=checkbox/range>` | Template controls (controls.md) |
| `transition: all .2s` | `Behavior on <prop> { ColorAnimation/NumberAnimation { duration: Theme.motionNormal } }` |
| `position:absolute` | `anchors` inside the parent |
| `overflow:hidden` | `clip: true` (rectangular) |
| `z-index` | `z` |
| `backdrop-filter: blur()` | effects.md "Blur and glass" |
| `mask-composite` gradient border | effects.md "Rounded clipping and gradient borders" |

## Tailwind

- Spacing scale: 1 unit = 4 px (`p-6` = 24, `gap-2.5` = 10).
- Radius: `rounded` 4, `rounded-md` 6, `rounded-lg` 8, `rounded-xl` 12, `rounded-2xl` 16,
  `rounded-3xl` 24, `rounded-full` = half the height.
- Font sizes: `text-xs` 12/16, `text-sm` 14/20, `text-base` 16/24, `text-lg` 18/28,
  `text-xl` 20/28, `text-2xl` 24/32, `text-3xl` 30/36 (size/line-height).
- Colors: resolve palette names to hex from the project's Tailwind config or the default
  palette of its Tailwind version (v3 hex; v4 oklch, which `html_to_spec.py` converts to sRGB
  hex: v4 `indigo-600` is `#4F39F6`, not v3's `#4F46E5`).
- Shadows: `shadow-sm` `0 1px 2px 0 rgb(0 0 0 / .05)`, `shadow` `0 1px 3px 0 rgb(0 0 0/.1), 0 1px 2px -1px rgb(0 0 0/.1)`,
  `shadow-md`, `shadow-lg` … from the config; each visible layer maps to one shadow item
  (Tailwind also emits transparent `0 0 #0000` ring/shadow slots: ignore them). `ring-2` is a
  spread shadow, drawn as a 2 px border outside the box.
