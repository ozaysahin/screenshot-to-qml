import QtQuick 2.15
import App.Style 1.0
import App.Controls 1.0

// Fuel / coolant bar: icon, low end, `count` segments lit up to `level`, high end.
Row {
    id: root

    property url icon
    property string low
    property string high
    property real level: 0
    property int count: 10

    height: 30
    spacing: Theme.space2 + 2
    Accessible.role: Accessible.ProgressBar
    Accessible.name: low + "–" + high + " " + Math.round(level * 100) + " %"

    SvgIcon {
        anchors.verticalCenter: parent.verticalCenter
        width: Theme.meterIcon
        height: Theme.meterIcon
        source: root.icon
        color: Theme.muted
    }

    Text {
        anchors.verticalCenter: parent.verticalCenter
        width: Theme.meterEnd
        height: Theme.lhSmall
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: root.low
        font: Theme.small
        color: Theme.muted
    }

    Row {
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.segmentGap

        Repeater {
            model: root.count

            Rectangle {
                required property int index

                width: Theme.segmentWidth
                height: Theme.segmentHeight
                radius: Theme.segmentRadius
                color: index < Math.round(root.level * root.count) ? Theme.text2 : Theme.dim
            }
        }
    }

    Text {
        anchors.verticalCenter: parent.verticalCenter
        width: Theme.meterEnd
        height: Theme.lhSmall
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        text: root.high
        font: Theme.small
        color: Theme.muted
    }
}
