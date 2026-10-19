import QtQuick
import App.Style

// Right-aligned time and date.
Column {
    id: root

    property string time
    property string date

    Text {
        anchors.right: parent.right
        height: 32
        verticalAlignment: Text.AlignVCenter
        text: root.time
        color: Theme.text
        font: Theme.clock
    }
    Text {
        anchors.right: parent.right
        height: 16
        verticalAlignment: Text.AlignVCenter
        text: root.date
        color: Theme.textMuted
        font: Theme.caption
    }
}
