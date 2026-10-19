# Controls

Interactive elements are built on `QtQuick.Templates` (`import QtQuick.Templates as T`). A
template brings the behavior: pressed, checked and hovered state, keyboard handling, focus,
touch and the accessibility role. You supply `background` and `contentItem` from the Theme. A
`MouseArea` + `Rectangle` "button" has none of that behavior. The `a11y` gate reports it.

`scaffold.py` copies a ready **control kit** into `qml/App/Controls` (module `App.Controls`).
Restyle the kit to the screenshot; don't write controls from scratch.

## Contents
- The kit
- Token contract
- Restyling to the screenshot
- Mapping (screenshot → control)
- State → property table
- Groups and models
- What the gates check
- Checklist

## The kit

| Control | File | States drawn | Keyboard |
| --- | --- | --- | --- |
| Button (`variant`: primary, secondary, ghost, danger; `glyph`; `compact`) | `Button.qml` | hover, pressed, focus ring, disabled | Tab, Space |
| IconButton (`glyph` or `iconComponent`; `text` = accessible name) | `IconButton.qml` | hover, pressed, checked, focus | Tab, Space |
| TextField (`error`, `glyph`, placeholder) | `TextField.qml` | hover, focus, error, disabled | Tab, typing |
| CheckBox (incl. `tristate`) | `CheckBox.qml` | checked, partial, hover, pressed, focus | Tab, Space |
| RadioButton | `RadioButton.qml` | checked, hover, pressed, focus | Tab, Space |
| Switch | `Switch.qml` | on/off, hover, pressed, focus, animated knob | Tab, Space |
| Slider (handle centered on the value) | `Slider.qml` | hover, pressed, focus | Tab, arrows |
| ComboBox (string lists or `textRole`) | `ComboBox.qml` | hover, pressed, open, focus; popup | Tab, arrows, Space |
| SpinBox (value field is the Tab stop) | `SpinBox.qml` | hover, pressed per button, focus | Tab, Up/Down |
| SegmentedControl (`model`, `currentIndex`, `activated`) | `SegmentedControl.qml` | checked, hover, pressed, focus | Tab per segment |
| TabBar + TabButton (underline) | `TabBar.qml`, `TabButton.qml` | current, hover, pressed, focus | Tab |
| ProgressBar | `ProgressBar.qml` | value | — |
| ToolTip | `ToolTip.qml` | — | Esc closes |
| FocusRing (shared outline) | `FocusRing.qml` | — | — |

- **Pick what you need.** `scaffold.py --controls Button,TextField,Switch` keeps only those
  (plus FocusRing). Delete kit files the screen does not use before delivery.
- **Example.** `examples/controls-gallery` uses every control in its states and passes all
  13 gates. `docs/img/controls.png` shows default, hover, pressed, focus and disabled.

## Token contract

The kit reads only these Theme names. `gen_theme.py` always emits them:

- **From the spec:** a spec token with the same name.
- **Alias:** a spec token with a common synonym, e.g. `accent: primary`.
- **Derived:** computed from other roles, e.g. `accentHover: Qt.darker(accent, 1.1)`.
- **Assumed:** a default value. List assumed values in the README.

| Role | Used for | Fallback |
| --- | --- | --- |
| `bg`, `surface`, `text`, `textMuted`, `placeholder` | page, control fill, labels, hints | brightest color, bg, highest contrast, tints of text |
| `accent`, `accentInk`, `accentHover`, `accentPressed` | primary button, checked, slider, focus | most saturated color; darker (light UI) or lighter (dark UI) |
| `border`, `borderStrong`, `track`, `knob` | outlines, off tracks, handles | tints of text on surface; white knob |
| `surfaceHover`, `surfacePressed` | hover/press on neutral controls | surface tinted 5 % / 10 % toward text |
| `danger`, `dangerInk`, `dangerHover`, `dangerPressed`, `dangerSoft` | danger button, error field | `#DC2626` (light) / `#F87171` (dark) |
| `focusRing`, `focusRingWidth` | keyboard focus outline | accent at 40 %, 3 px |
| `controlHeight`, `controlHeightSm`, `controlPadding`, `controlSpacing` | sizes | 40/32/12/8 desktop; 48/40/16/8 touch profiles |
| `radiusControl`, `borderWidth`, `touchTarget`, `motionFast`, `disabledOpacity` | shape, motion, disabled look | spec radius nearest 8; 1; 44; 120 ms; 0.45 |
| `fontControl`, `fontInput`, `fontIcon` | button labels, field text, icon glyphs | spec `button` / `body` tokens, else fontSans 14/16 |

Measured states override the defaults. When the screenshot shows a hovered row or a pressed
key, put that color in the spec under the role name (e.g. `accentHover`) and re-run
`gen_theme.py`.

## Restyling to the screenshot

- **Shape and color:** edit the kit file's `background` / `contentItem`. Keep the template
  root, `focusPolicy`, the state bindings (`down`, `hovered`, `checked`, `visualFocus`,
  `enabled`) and the `FocusRing`.
- **A variant the kit lacks** (outline-warning HMI key, pill chip): add a `variant` value in
  the same file rather than a second button file.
- **A control the kit lacks:** start from the matching template (`T.Dial`, `T.RangeSlider`,
  `T.Menu`, `T.Dialog`, `T.ScrollBar`) and copy the kit's conventions:
  - implicit size from background/content and paddings;
  - `focusPolicy: Qt.StrongFocus`;
  - a `FocusRing` on `visualFocus`;
  - Theme roles only;
  - `opacity: enabled ? 1 : Theme.disabledOpacity`.
- **CSS slider:** a CSS slider centers the handle on the value (`left: 60%; margin-left:
  -18px`). The kit's `Slider` does too, by keeping half a handle of padding on each side.
- **ComboBox popup:** the screenshot shows the closed state. The popup is styled from the
  same tokens (`assumed`).

## Mapping

| Seen in the screenshot | Kit / template |
| --- | --- |
| Button, chip that acts | `Button` (variants) · `T.RoundButton` · `T.ToolButton` |
| Icon-only button | `IconButton` with `text: qsTr("…")` as its accessible name |
| Toggle switch | `Switch` |
| Checkbox (incl. tri-state header) | `CheckBox` (`tristate`, `checkState: Qt.PartiallyChecked`) |
| Radio | `RadioButton` (siblings are auto-exclusive, or use a `T.ButtonGroup`) |
| Segmented control | `SegmentedControl` |
| Tab strip | `TabBar` + `TabButton` (bind a `StackLayout` to `currentIndex`) |
| Slider / seek bar | `Slider` |
| Text input, search | `TextField` (`placeholderText`, `glyph`) |
| Dropdown | `ComboBox` |
| Stepper | `SpinBox` |
| Progress | `ProgressBar` (non-interactive; set `Accessible.name`) |
| Menu, dialog, tooltip | `T.Menu`, `T.Dialog`, `ToolTip` |
| Scrollable list | `ListView` + `T.ScrollBar` |

## State → property table

| Visual state | Bind to |
| --- | --- |
| pressed | `control.down` |
| hover | `control.hovered` (desktop; touch profiles do not need it) |
| checked / selected | `control.checked`, `checkState` |
| disabled | `enabled: false`, styled through `control.enabled` (kit: `Theme.disabledOpacity`) |
| keyboard focus ring | `control.visualFocus` (keyboard only; `activeFocus` also fires on mouse) |
| text field focus | `control.activeFocus` (the caret shows it for mouse focus too) |
| error (text field) | the kit's `error` property |
| placeholder | `placeholderText` + `placeholderTextColor` |

Implement states that the screenshot does not show too, using derived or assumed values, and
list them in the README.

## Groups and models

- **Exclusive choices:** one `T.ButtonGroup`; buttons join with `T.ButtonGroup.group: group`
  (`SegmentedControl` does this for you).
- **Options come from a model** (`Repeater { model: options }`). Never copy-paste buttons.
- **Expose state to screens:** expose `currentIndex` / `value` and a signal; screens bind to
  it and backends read it.

## What the gates check

`check.py` renders the screen, then drives it with Tab, pointer hover and press
(`render.py --interact`). Every control it finds (Template controls, text fields) is checked:

| Gate | Fails when |
| --- | --- |
| `a11y` | an enabled control is never reached by Tab |
| `a11y` | keyboard focus does not change its pixels |
| `a11y` | a control has no accessible name |
| `states` | pressing an enabled control changes nothing (production) |
| `states` | hover changes nothing (warning, desktop only) |
| `i18n` | a visible string literal is not wrapped in `qsTr()` (production) |

`a11y` also warns about duplicate Tab stops, `MouseArea`s outside controls, and touch targets
under 44 px on embedded profiles.

## Checklist

- [ ] Every clickable thing is a kit/Template control, or has a written reason not to be.
- [ ] Tab reaches every enabled control in reading order, and the focus ring is visible.
- [ ] Icon-only buttons, sliders, combos, spin boxes and progress bars have `Accessible.name`.
- [ ] Pressed and (desktop) hover states are visible; disabled uses `enabled: false`.
- [ ] Touch targets are ≥ 44 px on touch profiles (HMI, kiosk, mobile).
- [ ] Unused kit files are deleted; `qmldir` lists only what is left.
