import QtQuick
import App.Style
import App.Controls

// Compact read-only chip with a glyph (shift, operator).
Rectangle {
    id: root

    property string glyph
    property string text

    implicitWidth: row.implicitWidth + 2 * 14
    implicitHeight: 36
    radius: Theme.radiusSm
    color: Theme.panel2
    border.color: Theme.border
    border.width: 1

    Row {
        id: row
        anchors.centerIn: parent
        spacing: Theme.gapSm
        Icon {
            anchors.verticalCenter: parent.verticalCenter
            glyph: root.glyph
            size: 14
            color: Theme.textMuted
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            color: Theme.text
            font: Theme.bodyStrong
        }
    }
}
