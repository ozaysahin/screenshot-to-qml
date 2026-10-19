pragma ComponentBehavior: Bound
import QtQuick
import App.Style
import App.Controls

Panel {
    id: root

    glyph: Icons.bell
    title: qsTr("Aktif Alarmlar")
    trailing: CountBadge {
        count: MockData.activeAlarmCount
    }

    Column {
        anchors.fill: parent
        spacing: Theme.gapSm
        Repeater {
            model: MockData.alarms
            delegate: AlarmItem {
                required property var modelData
                width: parent.width
                severity: modelData.severity
                code: modelData.code
                message: modelData.message
            }
        }
    }
}
