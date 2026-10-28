import QtQuick 2.15
import App.Style 1.0
import App.Controls 1.0

// Clock · outside temperature · date, centered above the telltales.
Item {
    implicitHeight: Theme.lhClock

    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        height: parent.height
        spacing: Theme.space4 + 2

        Text {
            anchors.verticalCenter: parent.verticalCenter
            height: Theme.lhClock
            verticalAlignment: Text.AlignVCenter
            text: MockData.clock
            font: Theme.clock
            color: Theme.text
        }

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 1
            height: Theme.space6
            color: Theme.border
        }

        Row {
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.space1 + 2

            SvgIcon {
                anchors.verticalCenter: parent.verticalCenter
                width: 22
                height: 22
                source: Qt.resolvedUrl("../../assets/icons/temperature.svg")
                color: Theme.muted
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                height: Theme.lhReading
                verticalAlignment: Text.AlignVCenter
                text: MockData.outside
                font: Theme.reading
                color: Theme.text2
            }
        }

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 1
            height: Theme.space6
            color: Theme.border
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            height: Theme.lhDate
            verticalAlignment: Text.AlignVCenter
            text: MockData.date
            font: Theme.date
            color: Theme.muted
        }
    }
}
