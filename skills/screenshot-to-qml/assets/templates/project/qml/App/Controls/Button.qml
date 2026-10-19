import QtQuick
import QtQuick.Templates as T
import App.Style

// Push button. variant: "primary" | "secondary" | "ghost" | "danger".
// `glyph` puts an icon-font glyph (Theme.fontIcon) before the text; `compact` uses the small height.
T.Button {
    id: control

    property string variant: "primary"
    property string glyph: ""
    property bool compact: false

    readonly property color fillColor: {
        if (variant === "primary")
            return down ? Theme.accentPressed : hovered ? Theme.accentHover : Theme.accent;
        if (variant === "danger")
            return down ? Theme.dangerPressed : hovered ? Theme.dangerHover : Theme.danger;
        if (variant === "secondary")
            return down ? Theme.surfacePressed : hovered ? Theme.surfaceHover : Theme.surface;
        return down ? Theme.surfacePressed : hovered ? Theme.surfaceHover : "transparent";
    }
    readonly property color inkColor: variant === "primary" ? Theme.accentInk : variant === "danger" ? Theme.dangerInk : Theme.text

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding)
    leftPadding: Theme.controlPadding
    rightPadding: Theme.controlPadding
    spacing: Theme.controlSpacing
    font: Theme.fontControl
    focusPolicy: Qt.StrongFocus
    opacity: enabled ? 1 : Theme.disabledOpacity

    contentItem: Item {
        implicitWidth: row.implicitWidth
        implicitHeight: row.implicitHeight

        Row {
            id: row

            anchors.centerIn: parent
            spacing: control.spacing

            Text {
                anchors.verticalCenter: parent.verticalCenter
                visible: control.glyph !== ""
                text: control.glyph
                font.family: Theme.fontIcon
                font.pixelSize: control.font.pixelSize + 2
                color: control.inkColor
                Accessible.ignored: true
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: control.text
                font: control.font
                color: control.inkColor
            }
        }
    }

    background: Rectangle {
        id: bg

        implicitWidth: implicitHeight * 2
        implicitHeight: control.compact ? Theme.controlHeightSm : Theme.controlHeight
        radius: Theme.radiusControl
        color: control.fillColor
        border.width: control.variant === "secondary" ? Theme.borderWidth : 0
        border.color: Theme.borderStrong

        FocusRing {
            visible: control.visualFocus
            baseRadius: bg.radius
        }
    }
}
