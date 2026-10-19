import QtQuick
import App.Style

// Small pill with a count, e.g. number of active alarms.
Rectangle {
    id: root

    property int count: 0

    implicitWidth: Math.max(28, label.implicitWidth + 2 * Theme.space2)
    implicitHeight: 24
    radius: height / 2
    color: Theme.danger
    Accessible.role: Accessible.StaticText
    Accessible.name: qsTr("%1 aktif").arg(root.count)

    Text {
        id: label
        anchors.centerIn: parent
        text: root.count
        color: Theme.white
        font: Theme.captionBold
    }
}
