# Effects: shadows, gradients, blur, clipping

## Contents
- Profile rules
- Shadows
- Gradients
- Blur and glass
- Rounded clipping and gradient borders
- Dashed and dotted borders
- Opacity of groups

## Profile rules

| Effect | desktop | embedded-gpu | embedded-sw |
| --- | --- | --- | --- |
| `RectangularShadow` (Qt 6.9+) | yes | yes (cheap, SDF) | no → flat darker border or nothing |
| `MultiEffect` shadow / blur / colorize | yes | shadows on a few items; no blur | no (needs shaders) |
| `Shape` gradients (`LinearGradient`, `RadialGradient`, `ConicalGradient`) | yes | yes | yes |
| `layer.enabled` | when needed | sparingly (costs an offscreen texture) | yes but slow |

Software rendering (`QT_QUICK_BACKEND=software`, also the `offscreen` platform) draws no shader
effects at all. `render.py` uses Xvfb on headless Linux so effects render during checks.

## Shadows

Measure: `shadow_fit.py input.png --spec design-spec.json` (every painted surface; match.py
writes the reliable ones into `style.shadow`) or `--box X Y W H --radius R` for one. It fits a
Gaussian-blurred copy of the box plus a smooth background to the ring of pixels around it, and
reports CSS values: `x y blur spread` and a color with alpha. Trust it when `hasShadow` is true;
`atBound` means a parameter hit its search limit (a neighbour's glow, a busy backdrop): measure
by hand. Multi-layer shadows come back as one equivalent layer (usually a negative spread);
that is the layer to build unless the design system says otherwise.

CSS `box-shadow: X Y B S color` on a rounded rect — pick by the project's minimum Qt
(`meta.minQt`; the `lint` gate flags types newer than it):

**Qt 6.9+: `RectangularShadow`** (cheap, one SDF quad; fine on embedded-gpu):

```qml
RectangularShadow {                       // import QtQuick.Effects
    anchors.fill: card                    // declared BEFORE the card so it paints below
    offset.x: X; offset.y: Y
    blur: B * 1.15                        // measured: blur 24 draws like CSS 21
    spread: S
    radius: card.radius
    color: Theme.shadowColor              // alpha from the CSS color
}
```

**Qt 6.8 (the default floor): `MultiEffect` shadow** on the card's layer:

```qml
Rectangle {
    id: card
    layer.enabled: true
    layer.effect: MultiEffect {           // import QtQuick.Effects
        shadowEnabled: true
        shadowColor: Theme.shadowColor
        shadowVerticalOffset: Y
        shadowHorizontalOffset: X
        shadowBlur: 1.0
        blurMax: 24                       // see the table: CSS blur 10
        autoPaddingEnabled: true
    }
}
```

| CSS blur | ≈ 4 | ≈ 10 | ≈ 27 | ≈ 37 |
| --- | --- | --- | --- | --- |
| `blurMax` (with `shadowBlur: 1.0`) | 12 | 24 | 48 | 64 (the maximum) |

Measured with `shadow_fit.py` on renders (the fitted spread comes out 1–4 px negative, so
leave `shadowScale` at 1). Each such card is a layer (an offscreen texture): on embedded-gpu
with many cards, use a stack of 2–3 translucent rounded rects behind the card instead.

- Multi-layer CSS shadows: one shadow per layer, or merge into one (what `shadow_fit.py`
  reports) and note it.
- Non-rectangular shapes (icons, text glow): the `MultiEffect` shadow on desktop.
- `inset 0 -6px 0 rgba(...)` (pressed edge): base rect in the shade color + the fill rect with
  `height: parent.height - 6` and the same radius on top (see `TouchButton.qml` in the example).
- Colored glows (`0 0 32px accent`): offset 0 and the accent color.
- embedded-sw draws neither: a 1 px darker border, or nothing (embedded.md).

## Gradients

| CSS | QML |
| --- | --- |
| `linear-gradient(180deg, a, b)` (top→bottom) | `Rectangle { gradient: Gradient { GradientStop {position: 0; color: a} GradientStop {position: 1; color: b} } }` |
| `linear-gradient(90deg, …)` | same with `orientation: Gradient.Horizontal` |
| `linear-gradient(0deg, a, b)` (bottom→top) | vertical with the stops reversed |
| any other angle (135deg…) | `Shape { ShapePath { fillGradient: LinearGradient { x1; y1; x2; y2 } } }` |
| `radial-gradient(circle, …)` | `ShapePath { fillGradient: RadialGradient { centerX; centerY; centerRadius; focalX; focalY } }` |
| `conic-gradient(from A, …)` | `ShapePath { fillGradient: ConicalGradient { angle; centerX; centerY } }` |

Measure: `gradient_fit.py input.png --spec design-spec.json` (nodes with a gradient fill) or
`--box X Y W H [--radius R] [--mask X Y W H …]`. It returns the CSS angle in (0°, 180°], 2–4
stops, and a `qt` block: `orientation` for 90°/180° (`Rectangle.gradient`), otherwise the
`LinearGradient` endpoints `x1 y1 x2 y2` in item px, computed as below.

CSS angle → endpoints for a W×H box: direction `d = (sin θ, −cos θ)`; half-length
`L = (|W sin θ| + |H cos θ|) / 2`; `x1,y1 = center − d·L`, `x2,y2 = center + d·L`.
Rounded shapes with angled gradients: `PathRectangle { radius }` (Qt 6.8+) in the ShapePath.
Area fills under chart lines: `LinearGradient` from the curve's top y to the plot bottom.

Gradient text (`background-clip: text`, the text run's `fillImage` in an HTML spec): draw the
gradient and mask it with the text. Desktop and embedded-gpu:

```qml
Item {
    implicitWidth: label.implicitWidth; implicitHeight: label.implicitHeight
    Text { id: label; text: qsTr("24°"); font: Theme.hero; visible: false; layer.enabled: true }
    Rectangle { id: fill; anchors.fill: label; visible: false; layer.enabled: true
                gradient: Gradient { orientation: Gradient.Horizontal
                                     GradientStop { position: 0; color: Theme.warm } GradientStop { position: 1; color: Theme.violet } } }
    MultiEffect { anchors.fill: label; source: fill; maskEnabled: true; maskSource: label }
}
```

Angled gradients: a `Shape` with `LinearGradient` endpoints (above) as the `fill` item. The text
item stays the one the checks read (`label`, hidden, same string and position). embedded-sw
has no MultiEffect: use the gradient's middle color on a plain `Text` and list it.

## Blur and glass

`backdrop-filter: blur(24px)` has no direct QML property. On desktop:

```qml
ShaderEffectSource { id: behind; sourceItem: background; sourceRect: Qt.rect(card.x, card.y, card.width, card.height); visible: false }
MultiEffect { source: behind; anchors.fill: card; blurEnabled: true; blur: 1.0; blurMax: 48; saturation: 0.4 }
```

then draw the translucent card (`Theme.glass`) on top. Big blurred color blobs in the
background: a `Shape` with a `RadialGradient` that fades to transparent is cheaper than
blurring a circle and looks the same.
On embedded profiles drop the blur and raise the card's fill alpha; list it as an approximation.

## Rounded clipping and gradient borders

- `clip: true` is rectangular. To clip children to a rounded card: give edge children matching
  per-corner radii, or use the "base + inset" trick (a colored base rect, and the content rect
  inset by the visible part), or `layer.enabled: true` + `layer.effect: MultiEffect { maskEnabled: true; maskSource: roundedMask }`
  on desktop.
- A left severity bar on a rounded row: base `Rectangle { color: severity; radius }` + a content
  rect at `x: 5` with `topRightRadius/bottomRightRadius` (see `AlarmItem.qml`).
- 1 px gradient border (`mask-composite`): `ShapePath` has no stroke gradient (only
  `fillGradient`, as of Qt 6.11). Fill an outer rounded shape with the gradient and draw the card
  fill inset by 1 px on top. With a translucent card fill the gradient shows through the middle,
  so use an even-odd `ShapePath` (outer `PathRectangle` + inner `PathRectangle`,
  `fillRule: ShapePath.OddEvenFill`) to fill only the 1 px ring.

## Dashed and dotted borders

`Rectangle.border` is always solid. Draw dashed or dotted borders with a `Shape` stroke and
leave the fill on the `Rectangle`:

```qml
Rectangle {
    id: chip
    color: Theme.surface
    radius: Theme.radiusSm
    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: Theme.border
            strokeWidth: 1
            fillColor: "transparent"
            strokeStyle: ShapePath.DashLine
            dashPattern: [4, 3]          // in units of strokeWidth: 4 px dash, 3 px gap
            PathRectangle {              // Qt 6.8+; half-pixel inset keeps a 1 px line crisp
                x: 0.5; y: 0.5
                width: chip.width - 1; height: chip.height - 1
                radius: chip.radius - 0.5
            }
        }
    }
}
```

Measure the dash and gap on a straight side with `probe.py edges`, not from the CSS. Browsers
stretch the gaps so that each side ends on a whole dash, so match the measured rhythm near the
middle of the longest side. For a dotted border, use `dashPattern: [0.01, 2]` with `capStyle:
ShapePath.RoundCap`. Round dots need `Shape.CurveRenderer`, because the default renderer draws
them square. In the baseline eval, dashed chips were the one region both arms missed.

## Opacity of groups

CSS `opacity` composites the whole element once. QML `opacity` multiplies down the tree, so
overlapping children show through each other. For a faded group (disabled card, overlay) set
`layer.enabled: true` on the group so it is flattened first. A single rect or a text is fine
without a layer.
