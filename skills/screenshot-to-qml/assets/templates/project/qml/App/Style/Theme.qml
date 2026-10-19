pragma Singleton
import QtQuick

// Placeholder Theme so a fresh scaffold runs. gen_theme.py design-spec.json replaces this file;
// every color, font, spacing and radius the UI uses lives here (App.Controls reads the roles).
QtObject {
    readonly property int designWidth: 1440
    readonly property int designHeight: 900

    // colors
    readonly property color bg: "#F8FAFC"
    readonly property color surface: "#FFFFFF"
    readonly property color text: "#0F172A"
    readonly property color accent: "#2563EB"

    // spacing
    readonly property int space1: 4
    readonly property int space2: 8
    readonly property int space3: 12
    readonly property int space4: 16
    readonly property int space5: 24

    // radius
    readonly property int radiusSm: 6
    readonly property int radiusMd: 8
    readonly property int radiusLg: 12

    // typography: family names as QFontDatabase reports them
    readonly property string fontSans: "Inter"
    readonly property string fontIcon: ""
    readonly property font body: Qt.font({
        family: fontSans,
        pixelSize: 14,
        weight: Font.Normal
    })
    readonly property font button: Qt.font({
        family: fontSans,
        pixelSize: 14,
        weight: Font.DemiBold
    })

    // control roles: the contract App.Controls uses (references/controls.md).
    // Aliases point at spec tokens; 'derived' follow from them; 'assumed' are defaults to confirm.
    readonly property color accentInk: "#FFFFFF"   // derived: best contrast on accent
    readonly property color accentHover: Qt.darker(accent, 1.1)   // derived
    readonly property color accentPressed: Qt.darker(accent, 1.2)   // derived
    readonly property color textMuted: Qt.tint(text, alpha(surface, 0.4))   // derived
    readonly property color placeholder: Qt.tint(text, alpha(surface, 0.55))   // derived
    readonly property color border: Qt.tint(surface, alpha(text, 0.14))   // derived
    readonly property color borderStrong: Qt.tint(surface, alpha(text, 0.28))   // derived
    readonly property color surfaceHover: Qt.tint(surface, alpha(text, 0.05))   // derived
    readonly property color surfacePressed: Qt.tint(surface, alpha(text, 0.1))   // derived
    readonly property color danger: "#DC2626"   // assumed
    readonly property color dangerInk: "#FFFFFF"   // derived: best contrast on danger
    readonly property color dangerHover: Qt.darker(danger, 1.1)   // derived
    readonly property color dangerPressed: Qt.darker(danger, 1.2)   // derived
    readonly property color dangerSoft: alpha(danger, 0.1)   // derived
    readonly property color focusRing: alpha(accent, 0.4)   // derived
    readonly property color track: borderStrong   // derived
    readonly property color knob: "#FFFFFF"   // assumed
    readonly property int controlHeight: 40   // assumed
    readonly property int controlHeightSm: 32   // assumed
    readonly property int controlPadding: 12   // assumed
    readonly property int controlSpacing: 8   // assumed
    readonly property int touchTarget: 44   // minimum hit area on touch profiles
    readonly property int radiusControl: radiusMd   // derived: spec radius closest to 8
    readonly property int borderWidth: 1   // assumed
    readonly property int focusRingWidth: 3   // assumed
    readonly property int motionFast: 120   // ms, assumed
    readonly property real disabledOpacity: 0.45   // assumed
    readonly property font fontControl: button
    readonly property font fontInput: body

    function alpha(c: color, a: real): color {
        return Qt.rgba(c.r, c.g, c.b, a);
    }
}
