import QtQuick
import QtQuick.Templates as T
import App.Style

// Square icon-only button. `text` is the accessible name (not drawn); `glyph` is an
// icon-font glyph, or set `iconComponent` to an svgtoqml-generated icon.
T.Button {
    id: control

    property string glyph: ""
    property Component iconComponent: null
    property color iconColor: checked ? Theme.accent : Theme.text

    implicitWidth: Theme.controlHeight
    implicitHeight: Theme.controlHeight
    padding: 0
    focusPolicy: Qt.StrongFocus
    opacity: enabled ? 1 : Theme.disabledOpacity
    Accessible.name: text

    contentItem: Item {
        Text {
            anchors.centerIn: parent
            visible: control.glyph !== ""
            text: control.glyph
            font.family: Theme.fontIcon
            font.pixelSize: Math.round(control.height * 0.45)
            color: control.iconColor
            Accessible.ignored: true
        }
        Loader {
            anchors.centerIn: parent
            active: control.iconComponent !== null
            sourceComponent: control.iconComponent
        }
    }

    background: Rectangle {
        id: bg

        radius: Theme.radiusControl
        color: control.down ? Theme.surfacePressed : control.checked ? (control.hovered ? Theme.surfacePressed : Theme.surfaceHover) : control.hovered ? Theme.surfaceHover : "transparent"

        FocusRing {
            visible: control.visualFocus
            baseRadius: bg.radius
        }
    }
}
