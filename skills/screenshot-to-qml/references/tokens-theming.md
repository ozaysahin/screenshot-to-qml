# Tokens and theming

## Module layout

```
qml/App/Style/     module App.Style     Theme (singleton), Icons (singleton)
qml/App/Controls/  module App.Controls  reusable controls; imports App.Style
qml/App/           module App           Main + screen components + MockData; imports both
```

The dependency only points down (App → Controls → Style), so there are no import cycles and
`qmllint -I qml` resolves everything.

## Theme singleton rules

```qml
pragma Singleton
import QtQuick

QtObject {
    readonly property int designWidth: 1920
    readonly property color panel: "#121821"
    readonly property color okSoft: "#2422C55E"      // rgba(34,197,94,0.14)
    readonly property int space5: 24
    readonly property int radiusLg: 14
    readonly property string fontSans: "Barlow"
    readonly property font heading: Qt.font({ family: fontSans, pixelSize: 18, weight: Font.DemiBold })
    function alpha(c: color, a: real): color { return Qt.rgba(c.r, c.g, c.b, a) }
}
```

- **Flat names.** `Theme.panel`, `Theme.space5`, `Theme.heading`. Nested `QtObject` groups
  (`Theme.colors.panel`) make qmllint report "member not found".
- **Colors:** `#RRGGBB`, or `#AARRGGBB` for alpha (alpha **first** — CSS `#RRGGBBAA` order is
  wrong in QML). Alpha byte = `round(a × 255)`; keep the CSS `rgba()` in a comment.
- **Never start a token with `on` + capital** (`onAccent`): QML treats it as a signal handler
  and the whole module fails to load. Use `accentInk`, `primaryInk`.
- **Font tokens** are `font` values built with `Qt.font({...})`; include `letterSpacing` there.
- **Derived colors** (hover shades, chart fills at x% alpha) are computed in the Theme
  (`alpha()`, `Qt.darker/lighter`) or stored as tokens; components do not call `Qt.rgba`.
- **Sizes that are part of the design language** (spacing scale, radii, control heights,
  column widths, touch-target size) live in the Theme. Component-internal geometry that has no
  meaning outside the component (a 2 px tick, a chart's padding) may stay local.
- Components never contain color/font literals; `quality_gate.py --mode production` fails them.

## Naming

| Kind | Pattern | Examples |
| --- | --- | --- |
| surfaces | noun | `bg`, `surface`, `panel`, `panel2`, `border`, `borderStrong` |
| text | `text`, `textMuted`, `textDim`, `placeholder` | |
| brand/state | `accent`, `ok`, `warn`, `danger`, `info` + `Soft`, `Deep`, `Ink` | `dangerSoft`, `accentInk` |
| spacing | `space1…spaceN` (scale), `gapXs…gapLg` (one-offs) | |
| radius | `radiusXs…radiusXl`, `radiusPill` | |
| fonts | `fontSans`, `fontMono`, `fontIcon` + role tokens | `title`, `heading`, `body`, `caption`, `kpiValue` |
| motion | `motionFast`, `motionNormal` | |

## Dark and light

Two palettes, one API:

```qml
QtObject {
    property bool dark: true
    readonly property color bg: dark ? "#0B0F14" : "#F6F7FB"
    readonly property color text: dark ? "#E6EDF5" : "#0F172A"
}
```

Bind `Theme.dark` to a setting or `Application.styleHints.colorScheme === Qt.Dark` (Qt 6.5+).
Only colors switch; sizes and fonts stay. Measure both variants when the user provides both.

## Control roles

`gen_theme.py` ends the Theme with the **control contract**: the role names the kit in
`App.Controls` reads (`accent`, `accentInk`, `accentHover`, `accentPressed`, `surface`,
`surfaceHover`, `surfacePressed`, `border`, `borderStrong`, `text`, `textMuted`,
`placeholder`, `danger…`, `focusRing`, `track`, `knob`, control sizes, `fontControl`,
`fontInput`, `fontIcon`). Each role is written in one of four ways:

- **From the spec:** a spec token with the same name, used as is.
- **Alias:** points at a spec token with a common synonym, e.g. `accent: primary`,
  `surface: panel`.
- **Derived:** computed in the Theme from other roles, e.g. `Qt.darker(accent, 1.1)` on
  light UIs, `Qt.lighter` on dark ones, or `Qt.tint(surface, alpha(text, 0.05))`.
- **Assumed:** a default, marked `// assumed` in the Theme. Confirm these or list them in the
  README.

Touch profiles (`embedded-gpu`, `embedded-sw`, or a design narrower than 600 px) get 48 px
controls and 16 px text. Full table: controls.md → Token contract.

## From spec to Theme

Every `tokens.color` entry becomes a color property, `tokens.space`/`radius` become ints,
`tokens.typeScale` entries become font tokens named by role (largest → `display`/`title`,
body text → `body`, small → `caption`). Keep the order of the spec so reviews can diff them.
