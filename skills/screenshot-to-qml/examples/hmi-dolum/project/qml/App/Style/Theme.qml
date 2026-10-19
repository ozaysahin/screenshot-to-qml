pragma Singleton
import QtQuick

// Design tokens for the Hat 3 filling-line HMI.
// Source: design-spec.json (tokens.color / space / radius / typeScale).
// Every visual value used by the UI lives here; components never hard-code
// colors or pixel sizes. Alpha colors are #AARRGGBB (Qt order), with the CSS
// rgba() source noted next to them.
QtObject {
    // ---- canvas ---------------------------------------------------------
    readonly property int designWidth: 1920
    readonly property int designHeight: 1080

    // ---- colors ---------------------------------------------------------
    readonly property color bg: "#0B0F14"
    readonly property color panel: "#121821"
    readonly property color panel2: "#18212D"
    readonly property color border: "#243042"
    readonly property color text: "#E6EDF5"
    readonly property color textMuted: "#8A98AB"
    readonly property color textDim: "#5B6878"
    readonly property color accent: "#38BDF8"
    readonly property color accentDeep: "#0284C7"
    readonly property color ok: "#22C55E"
    readonly property color warn: "#F59E0B"
    readonly property color warnDeep: "#B45309"
    readonly property color danger: "#EF4444"
    readonly property color white: "#FFFFFF"
    readonly property color accentSoft: "#1F38BDF8"   // rgba(56,189,248,0.12)
    readonly property color okSoft: "#2422C55E"       // rgba(34,197,94,0.14)
    readonly property color okLine: "#5922C55E"       // rgba(34,197,94,0.35)
    readonly property color okGlow: "#3822C55E"       // rgba(34,197,94,0.22)
    readonly property color warnSoft: "#24F59E0B"     // rgba(245,158,11,0.14)
    readonly property color dangerSoft: "#24EF4444"   // rgba(239,68,68,0.14)
    readonly property color accentInk: "#04121C"
    readonly property color okInk: "#052E14"
    readonly property color pressShade: "#40000000"   // rgba(0,0,0,0.25)

    // ---- spacing / radius ---------------------------------------------
    readonly property int space1: 4
    readonly property int space2: 8
    readonly property int space3: 12
    readonly property int space4: 16
    readonly property int space5: 24
    readonly property int space6: 32
    readonly property int gapXs: 6
    readonly property int gapSm: 10
    readonly property int gapMd: 14
    readonly property int gapLg: 20
    readonly property int radiusXs: 2
    readonly property int radiusSm: 8
    readonly property int radiusMd: 10
    readonly property int radiusLg: 14
    readonly property int radiusXl: 16

    // ---- sizes ----------------------------------------------------------
    readonly property int topBarHeight: 76
    readonly property int statusBarHeight: 44
    readonly property int sideColumnWidth: 520
    readonly property int touchButtonHeight: 80
    readonly property int emergencyButtonHeight: 100

    // ---- typography -----------------------------------------------------
    // Family names are the ones QFontDatabase reports for assets/fonts.
    readonly property string fontSans: "Barlow"
    readonly property string fontMono: "JetBrains Mono"
    readonly property string fontIcon: "Font Awesome 7 Free"

    readonly property font kpiValue: Qt.font({
        family: fontMono,
        pixelSize: 52,
        weight: Font.Medium,
        letterSpacing: -1
    })
    readonly property font gaugeValue: Qt.font({
        family: fontMono,
        pixelSize: 30,
        weight: Font.Bold
    })
    readonly property font clock: Qt.font({
        family: fontMono,
        pixelSize: 28,
        weight: Font.Medium,
        letterSpacing: -0.5
    })
    readonly property font statValue: Qt.font({
        family: fontMono,
        pixelSize: 28,
        weight: Font.Medium
    })
    readonly property font sliderValue: Qt.font({
        family: fontMono,
        pixelSize: 22,
        weight: Font.Medium
    })
    readonly property font unitLarge: Qt.font({
        family: fontMono,
        pixelSize: 18,
        weight: Font.Normal
    })
    readonly property font unitMedium: Qt.font({
        family: fontMono,
        pixelSize: 16,
        weight: Font.Medium
    })
    readonly property font mono15: Qt.font({
        family: fontMono,
        pixelSize: 15,
        weight: Font.Normal
    })
    readonly property font mono14: Qt.font({
        family: fontMono,
        pixelSize: 14,
        weight: Font.Normal
    })
    readonly property font mono14Strong: Qt.font({
        family: fontMono,
        pixelSize: 14,
        weight: Font.Medium
    })
    readonly property font mono13: Qt.font({
        family: fontMono,
        pixelSize: 13,
        weight: Font.Normal
    })
    readonly property font mono12: Qt.font({
        family: fontMono,
        pixelSize: 12,
        weight: Font.Normal
    })

    readonly property font emergency: Qt.font({
        family: fontSans,
        pixelSize: 26,
        weight: Font.Bold,
        letterSpacing: 2
    })
    readonly property font title: Qt.font({
        family: fontSans,
        pixelSize: 22,
        weight: Font.DemiBold
    })
    readonly property font button: Qt.font({
        family: fontSans,
        pixelSize: 20,
        weight: Font.Bold,
        letterSpacing: 1
    })
    readonly property font heading: Qt.font({
        family: fontSans,
        pixelSize: 18,
        weight: Font.DemiBold
    })
    readonly property font pill: Qt.font({
        family: fontSans,
        pixelSize: 16,
        weight: Font.Bold,
        letterSpacing: 1
    })
    readonly property font segment: Qt.font({
        family: fontSans,
        pixelSize: 16,
        weight: Font.Medium
    })
    readonly property font segmentSelected: Qt.font({
        family: fontSans,
        pixelSize: 16,
        weight: Font.DemiBold
    })
    readonly property font bodyStrong: Qt.font({
        family: fontSans,
        pixelSize: 15,
        weight: Font.Medium
    })
    readonly property font body: Qt.font({
        family: fontSans,
        pixelSize: 15,
        weight: Font.Normal
    })
    readonly property font small: Qt.font({
        family: fontSans,
        pixelSize: 14,
        weight: Font.Normal
    })
    readonly property font smallMedium: Qt.font({
        family: fontSans,
        pixelSize: 14,
        weight: Font.Medium
    })
    readonly property font smallStrong: Qt.font({
        family: fontSans,
        pixelSize: 14,
        weight: Font.DemiBold
    })
    readonly property font caption: Qt.font({
        family: fontSans,
        pixelSize: 13,
        weight: Font.Normal
    })
    readonly property font captionStrong: Qt.font({
        family: fontSans,
        pixelSize: 13,
        weight: Font.DemiBold
    })
    readonly property font captionBold: Qt.font({
        family: fontSans,
        pixelSize: 13,
        weight: Font.Bold
    })
    readonly property font eyebrow: Qt.font({
        family: fontSans,
        pixelSize: 12,
        weight: Font.DemiBold,
        letterSpacing: 1.6
    })

    // ---- charts -------------------------------------------------------
    readonly property real chartAreaOpacity: 0.28

    // Returns `c` with alpha `a` (keeps derived colors inside the Style module).
    function alpha(c: color, a: real): color {
        return Qt.rgba(c.r, c.g, c.b, a);
    }

    // ---- motion ---------------------------------------------------------
    readonly property int motionFast: 120
    readonly property int motionNormal: 200
}
