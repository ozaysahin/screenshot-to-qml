import QtQuick
import QtQuick.Layouts
import App.Style

// Footer: PLC link, recipe, lot, software version.
Rectangle {
    id: root

    implicitHeight: Theme.statusBarHeight
    color: Theme.panel

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 1
        color: Theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.topMargin: 1
        anchors.leftMargin: Theme.space6
        anchors.rightMargin: Theme.space6
        spacing: Theme.space6

        RowLayout {
            spacing: Theme.space2
            Rectangle {
                Layout.preferredWidth: 8
                Layout.preferredHeight: 8
                radius: width / 2
                color: Theme.ok
            }
            Text {
                text: qsTr("PLC bağlı")
                color: Theme.ok
                font: Theme.small
            }
        }
        RowLayout {
            spacing: 0
            Text {
                Layout.alignment: Qt.AlignBaseline
                text: qsTr("Reçete: ")
                color: Theme.textMuted
                font: Theme.small
            }
            Text {
                Layout.alignment: Qt.AlignBaseline
                text: MockData.recipe
                color: Theme.text
                font: Theme.smallMedium
            }
        }
        RowLayout {
            spacing: 0
            Text {
                Layout.alignment: Qt.AlignBaseline
                text: qsTr("Parti: ")
                color: Theme.textMuted
                font: Theme.small
            }
            Text {
                Layout.alignment: Qt.AlignBaseline
                text: MockData.lot
                color: Theme.text
                font: Theme.mono14Strong
            }
        }
        Item {
            Layout.fillWidth: true
        }
        Text {
            text: MockData.version
            color: Theme.textMuted
            font: Theme.mono14
        }
    }
}
