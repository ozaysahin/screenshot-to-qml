pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import App.Style
import App.Controls

Panel {
    id: root

    glyph: Icons.droplet
    title: qsTr("Tank Seviyeleri")
    aside: qsTr("Son güncelleme 2 sn önce")

    RowLayout {
        id: tankRow
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Theme.gapLg
        Repeater {
            model: MockData.tanks
            delegate: TankGauge {
                required property var modelData
                // CSS flex: 1 1 0 -> equal columns regardless of content width
                Layout.preferredWidth: (tankRow.width - 2 * tankRow.spacing) / 3
                name: modelData.name
                content: modelData.content
                level: modelData.level
                liters: modelData.liters
                capacity: modelData.capacity
                warning: modelData.warning
            }
        }
    }

    GridLayout {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        columns: 2
        columnSpacing: Theme.space4
        EnvStat {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            glyph: Icons.temperatureHalf
            label: qsTr("Ürün Sıcaklığı")
            value: "4,2"
            unit: "°C"
        }
        EnvStat {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            glyph: Icons.gaugeHigh
            label: qsTr("Aktif Nozul")
            value: "6/6"
            unit: qsTr("hazır")
        }
    }
}
