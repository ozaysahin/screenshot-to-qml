import QtQuick
import App.Style

// Line state pill: glowing dot, state label and runtime.
Rectangle {
    id: root

    property string label
    property string runtime

    implicitWidth: row.implicitWidth + 16 + 20
    implicitHeight: 44
    radius: height / 2
    color: Theme.okSoft
    border.color: Theme.okLine
    border.width: 1
    Accessible.role: Accessible.StaticText
    Accessible.name: label + " " + runtime

    Row {
        id: row
        x: 16
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.space3

        Item {
            width: 12
            height: 12
            anchors.verticalCenter: parent.verticalCenter
            Rectangle {
                anchors.centerIn: parent
                width: 20
                height: 20
                radius: width / 2
                color: Theme.okGlow
            }
            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: Theme.ok
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.label
            color: Theme.ok
            font: Theme.pill
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.runtime
            color: Theme.textMuted
            font: Theme.mono15
        }
    }
}
