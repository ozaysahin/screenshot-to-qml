import QtQuick 2.15
import App.Style 1.0
import App.Controls 1.0

// Now playing: source tile, station and programme, volume.
Card {
    implicitHeight: Theme.mediaHeight

    Rectangle {
        id: cover

        x: 1 + Theme.space3 + 2
        anchors.verticalCenter: parent.verticalCenter
        width: Theme.cover
        height: Theme.cover
        radius: Theme.radiusMd
        color: Theme.accentSoft

        SvgIcon {
            anchors.centerIn: parent
            width: 26
            height: 26
            source: Qt.resolvedUrl("../../assets/icons/radio.svg")
            color: Theme.accent
        }
    }

    Column {
        x: cover.x + cover.width + Theme.space3 + 2
        anchors.verticalCenter: parent.verticalCenter

        Text {
            height: Theme.lhRoute
            verticalAlignment: Text.AlignVCenter
            text: MockData.mediaTitle
            font: Theme.route
            color: Theme.text
        }

        Text {
            height: Theme.lhMediaSub
            verticalAlignment: Text.AlignVCenter
            text: MockData.mediaSubtitle
            font: Theme.mediaSub
            color: Theme.muted
        }
    }

    Row {
        anchors.right: parent.right
        anchors.rightMargin: 1 + Theme.space5
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.space2
        Accessible.role: Accessible.StaticText
        Accessible.name: qsTr("Ses seviyesi %1").arg(MockData.volume)

        SvgIcon {
            anchors.verticalCenter: parent.verticalCenter
            width: 22
            height: 22
            source: Qt.resolvedUrl("../../assets/icons/volume.svg")
            color: Theme.muted
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            height: Theme.lhSmall
            verticalAlignment: Text.AlignVCenter
            text: MockData.volume
            font: Theme.small
            color: Theme.muted
        }
    }
}
