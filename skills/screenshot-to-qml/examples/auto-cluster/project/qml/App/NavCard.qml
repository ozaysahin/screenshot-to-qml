import QtQuick 2.15
import App.Style 1.0
import App.Controls 1.0

// Turn-by-turn card: maneuver tile, distance and street, progress to the turn, route summary.
Card {
    id: root

    radius: Theme.radiusXl
    implicitHeight: Theme.navHeight

    Item {
        id: content

        anchors.fill: parent
        anchors.margins: 1
        anchors.leftMargin: 1 + Theme.space6
        anchors.rightMargin: 1 + Theme.space6
        anchors.topMargin: 1 + Theme.space5 + 2

        Rectangle {
            id: maneuver

            width: Theme.maneuver
            height: Theme.maneuver
            radius: Theme.radiusLg
            color: Theme.accentSoft

            SvgIcon {
                anchors.centerIn: parent
                width: 56
                height: 56
                source: Qt.resolvedUrl("../../assets/icons/corner-up-right.svg")
                color: Theme.accent
            }
        }

        Column {
            id: textColumn

            x: maneuver.width + Theme.space5

            Text {
                height: Theme.lhNavDistance
                verticalAlignment: Text.AlignVCenter
                text: MockData.navDistance
                font: Theme.navDistance
                color: Theme.text
            }

            Text {
                height: Theme.lhStreet
                verticalAlignment: Text.AlignVCenter
                text: MockData.navStreet
                font: Theme.street
                color: Theme.text2
            }

            Text {
                topPadding: 2
                height: Theme.lhCaption + 2
                verticalAlignment: Text.AlignVCenter
                text: MockData.navTowards
                font: Theme.caption
                color: Theme.muted
            }
        }

        Rectangle {
            id: progress

            y: Math.max(maneuver.height, textColumn.height) + Theme.space5
            width: parent.width
            height: Theme.progressHeight
            radius: height / 2
            color: Theme.track
            Accessible.role: Accessible.ProgressBar
            Accessible.name: qsTr("Dönüşe kalan mesafe")

            Rectangle {
                width: parent.width * MockData.navProgress
                height: parent.height
                radius: height / 2
                color: Theme.accent
            }
        }

        // three items spread like CSS justify-content: space-between
        Row {
            id: routeRow

            y: progress.y + progress.height + Theme.space4 + 2
            width: parent.width
            spacing: (width - (routeItems.itemAt(0) ? routeItems.itemAt(0).width + routeItems.itemAt(1).width + routeItems.itemAt(2).width : 0)) / 2

            Repeater {
                id: routeItems

                model: MockData.route

                Row {
                    id: routeItem

                    required property var modelData

                    height: Theme.lhRoute
                    spacing: Theme.space2

                    SvgIcon {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 20
                        height: 20
                        source: Qt.resolvedUrl("../../assets/icons/" + routeItem.modelData.icon + ".svg")
                        color: Theme.muted
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        height: Theme.lhRoute
                        verticalAlignment: Text.AlignVCenter
                        text: routeItem.modelData.text
                        font: Theme.route
                        color: Theme.text2
                    }
                }
            }
        }
    }
}
