import QtQuick
import QtQuick.Layouts
import App.Style
import App.Controls

// Header: brand, line state, shift/operator chips and clock.
Rectangle {
    id: root

    implicitHeight: Theme.topBarHeight
    color: Theme.panel

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Theme.border
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.space6
        anchors.rightMargin: Theme.space6
        anchors.bottomMargin: 1
        spacing: Theme.space5

        RowLayout {
            Layout.preferredWidth: Theme.sideColumnWidth
            Layout.fillWidth: false
            spacing: Theme.gapMd
            Rectangle {
                Layout.preferredWidth: 44
                Layout.preferredHeight: 44
                radius: Theme.radiusMd
                color: Theme.accentSoft
                Icon {
                    anchors.centerIn: parent
                    glyph: Icons.industry
                    size: 20
                    color: Theme.accent
                }
            }
            Column {
                Layout.fillWidth: true
                Text {
                    height: 16
                    verticalAlignment: Text.AlignVCenter
                    text: MockData.company
                    color: Theme.textMuted
                    font: Theme.eyebrow
                }
                Text {
                    height: 28
                    verticalAlignment: Text.AlignVCenter
                    text: MockData.station
                    color: Theme.text
                    font: Theme.title
                    Accessible.role: Accessible.Heading
                }
            }
        }

        StatusPill {
            label: qsTr("ÇALIŞIYOR")
            runtime: MockData.runtime
        }

        Item {
            Layout.fillWidth: true
        }

        InfoChip {
            glyph: Icons.calendar
            text: MockData.shift
        }
        InfoChip {
            Layout.leftMargin: 28 - Theme.space5
            glyph: Icons.user
            text: qsTr("Operatör: %1").arg(MockData.operatorName)
        }
        ClockLabel {
            Layout.leftMargin: 28 - Theme.space5
            time: MockData.time
            date: MockData.date
        }
    }
}
