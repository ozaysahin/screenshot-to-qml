pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import App.Style
import App.Controls

// Vertical tank level gauge with name, content, volume and status tag.
ColumnLayout {
    id: root

    property string name
    property string content
    property real level: 0
    property string liters
    property string capacity
    property bool warning: false

    readonly property int vesselBorder: 2
    readonly property int vesselInner: 548 - 2 * vesselBorder

    spacing: Theme.gapMd
    Accessible.role: Accessible.ProgressBar
    Accessible.name: qsTr("%1 %2, yüzde %3").arg(name).arg(content).arg(Math.round(level * 100))

    Rectangle {
        id: vessel
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredWidth: 124
        Layout.preferredHeight: 548
        radius: Theme.radiusXl
        color: Theme.panel2

        Rectangle {
            id: fill
            x: root.vesselBorder
            width: parent.width - 2 * root.vesselBorder
            height: root.level * root.vesselInner
            y: root.vesselBorder + root.vesselInner - height
            bottomLeftRadius: Theme.radiusXl - root.vesselBorder
            bottomRightRadius: Theme.radiusXl - root.vesselBorder
            gradient: Gradient {
                GradientStop {
                    position: 0.0
                    color: root.warning ? Theme.warn : Theme.accent
                }
                GradientStop {
                    position: 1.0
                    color: root.warning ? Theme.warnDeep : Theme.accentDeep
                }
            }
        }

        Repeater {
            model: [0.25, 0.5, 0.75]
            delegate: Rectangle {
                required property real modelData
                x: root.vesselBorder
                y: root.vesselBorder + modelData * root.vesselInner
                width: 16
                height: 2
                color: Theme.border
            }
        }

        // Border drawn last so the fill never covers it.
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: "transparent"
            border.color: Theme.border
            border.width: root.vesselBorder
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: root.vesselBorder + 16
            height: 36
            verticalAlignment: Text.AlignVCenter
            text: Math.round(root.level * 100) + "%"
            color: Theme.text
            font: Theme.gaugeValue
        }
    }

    Text {
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredHeight: 22
        verticalAlignment: Text.AlignVCenter
        text: root.name
        color: Theme.text
        font: Theme.heading
    }
    Text {
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredHeight: 18
        Layout.topMargin: -10
        verticalAlignment: Text.AlignVCenter
        text: root.content
        color: Theme.textMuted
        font: Theme.body
    }
    Row {
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredHeight: 18
        Text {
            height: 18
            verticalAlignment: Text.AlignVCenter
            text: root.liters
            color: Theme.text
            font: Theme.mono14Strong
        }
        Text {
            height: 18
            verticalAlignment: Text.AlignVCenter
            text: " / " + root.capacity + " L"
            color: Theme.textMuted
            font: Theme.mono14
        }
    }
    StatusTag {
        Layout.alignment: Qt.AlignHCenter
        text: root.warning ? qsTr("Düşük") : qsTr("Normal")
        glyph: root.warning ? Icons.triangleExclamation : ""
        tint: root.warning ? Theme.warn : Theme.ok
        tintSoft: root.warning ? Theme.warnSoft : Theme.okSoft
    }
}
