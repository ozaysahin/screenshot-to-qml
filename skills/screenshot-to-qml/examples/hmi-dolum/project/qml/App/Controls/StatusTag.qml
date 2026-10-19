import QtQuick
import App.Style

// Pill tag with optional leading glyph ("Normal", "Düşük").
Rectangle {
    id: root

    property string text
    property string glyph
    property color tint: Theme.ok
    property color tintSoft: Theme.okSoft

    implicitWidth: row.implicitWidth + 2 * 10
    implicitHeight: 26
    radius: height / 2
    color: tintSoft

    Row {
        id: row
        anchors.centerIn: parent
        spacing: Theme.gapXs

        Icon {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.glyph.length > 0
            glyph: root.glyph
            size: 11
            color: root.tint
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            color: root.tint
            font: Theme.captionStrong
        }
    }
}
