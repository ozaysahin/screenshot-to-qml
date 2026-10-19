import QtQuick
import QtQuick.Templates as T
import App.Style

// Large touch button for HMI panels.
// variant: "success" | "warningOutline" | "danger"
T.Button {
    id: control

    property string variant: "success"
    property string glyph
    property int glyphSize: 20

    readonly property color fillColor: variant === "danger" ? Theme.danger : variant === "warningOutline" ? Theme.panel2 : Theme.ok
    readonly property color contentColor: variant === "danger" ? Theme.white : variant === "warningOutline" ? Theme.warn : Theme.okInk

    implicitWidth: 200
    implicitHeight: Theme.touchButtonHeight
    font: Theme.button
    opacity: enabled ? 1.0 : 0.35
    focusPolicy: Qt.StrongFocus

    background: Rectangle {
        radius: Theme.radiusLg
        color: control.down ? Qt.darker(control.fillColor, 1.15) : control.fillColor
        border.color: control.variant === "warningOutline" ? Theme.warn : "transparent"
        border.width: control.variant === "warningOutline" ? 2 : 0

        // keyboard focus ring outside the button, for every variant
        Rectangle {
            anchors.fill: parent
            anchors.margins: -4
            radius: parent.radius + 4
            color: "transparent"
            border.color: Theme.accent
            border.width: 2
            visible: control.visualFocus
        }

        // CSS "inset 0 -6px 0" press edge for the danger variant: a 6 px band at
        // the bottom whose top edge follows the rounded corners.
        Rectangle {
            visible: control.variant === "danger"
            anchors.fill: parent
            radius: parent.radius
            color: Theme.pressShade
        }
        Rectangle {
            visible: control.variant === "danger"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: parent.height - 6
            radius: parent.radius
            color: control.down ? Qt.darker(control.fillColor, 1.15) : control.fillColor
        }
    }

    contentItem: Item {
        implicitWidth: row.implicitWidth
        implicitHeight: row.implicitHeight
        Row {
            id: row
            anchors.centerIn: parent
            spacing: Theme.gapMd
            Icon {
                anchors.verticalCenter: parent.verticalCenter
                glyph: control.glyph
                size: control.glyphSize
                color: control.contentColor
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: control.text
                font: control.font
                color: control.contentColor
            }
        }
    }
}
