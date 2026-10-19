import QtQuick
import App.Style
import App.Controls

Panel {
    id: root

    glyph: Icons.gaugeHigh
    title: qsTr("Dolum Basıncı")

    trailing: Row {
        spacing: Theme.gapLg
        Row {
            spacing: Theme.space2
            anchors.verticalCenter: parent.verticalCenter
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 16
                height: 3
                radius: Theme.radiusXs
                color: Theme.accent
            }
            Text {
                text: qsTr("Ölçülen")
                color: Theme.textMuted
                font: Theme.small
            }
        }
        Row {
            spacing: Theme.space2
            anchors.verticalCenter: parent.verticalCenter
            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.space1
                Rectangle {
                    width: 6
                    height: 3
                    color: Theme.warn
                }
                Rectangle {
                    width: 6
                    height: 3
                    color: Theme.warn
                }
            }
            Text {
                text: qsTr("Hedef 2,40 bar")
                color: Theme.textMuted
                font: Theme.small
            }
        }
    }

    LineChart {
        anchors.fill: parent
        values: MockData.pressure
        yMin: 2.1
        yMax: 2.6
        yTicks: [2.1, 2.2, 2.3, 2.4, 2.5, 2.6]
        xLabels: MockData.pressureTimeLabels
        setpoint: MockData.pressureSetpoint
    }
}
