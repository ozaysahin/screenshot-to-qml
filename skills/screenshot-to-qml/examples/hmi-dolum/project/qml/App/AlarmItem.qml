import QtQuick
import App.Style
import App.Controls

// Alarm row. severity: "danger" | "warning" | "info" drives bar, tile and glyph.
Rectangle {
    id: root

    property string severity: "info"
    property string code
    property string message

    readonly property color tint: severity === "danger" ? Theme.danger : severity === "warning" ? Theme.warn : Theme.accent
    readonly property color tintSoft: severity === "danger" ? Theme.dangerSoft : severity === "warning" ? Theme.warnSoft : Theme.accentSoft
    readonly property string glyph: severity === "danger" ? Icons.circleExclamation : severity === "warning" ? Icons.triangleExclamation : Icons.circleInfo

    implicitHeight: 64
    radius: Theme.radiusMd
    color: tint          // shows through as the 5 px severity bar on the left
    Accessible.role: Accessible.ListItem
    Accessible.name: code + " " + message

    Rectangle {
        x: 5
        width: parent.width - 5
        height: parent.height
        color: Theme.panel2
        topRightRadius: Theme.radiusMd
        bottomRightRadius: Theme.radiusMd
    }

    Rectangle {
        id: tile
        x: 5 + 14
        anchors.verticalCenter: parent.verticalCenter
        width: 32
        height: 32
        radius: Theme.radiusSm
        color: root.tintSoft
        Icon {
            anchors.centerIn: parent
            glyph: root.glyph
            size: 14
            color: root.tint
        }
    }

    Column {
        anchors.left: tile.right
        anchors.leftMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        Text {
            height: 16
            verticalAlignment: Text.AlignVCenter
            text: root.code
            color: Theme.textMuted
            font: Theme.mono12
        }
        Text {
            height: 20
            verticalAlignment: Text.AlignVCenter
            text: root.message
            color: Theme.text
            font: Theme.bodyStrong
        }
    }
}
