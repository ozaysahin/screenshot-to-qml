import QtQuick
import App.Style
import App.Controls

// KPI tile: label, large mono value with unit, footnote with optional trend delta.
Rectangle {
    id: root

    property string glyph
    property string label
    property string value
    property string unit
    property string foot
    property string delta
    property string trend   // "up" | "down" | ""

    implicitHeight: 164
    radius: Theme.radiusLg
    color: Theme.panel
    border.color: Theme.border
    border.width: 1
    Accessible.role: Accessible.StaticText
    Accessible.name: label + " " + value + " " + unit

    Row {
        id: labelRow
        x: 1 + Theme.space5
        y: 1 + 20
        height: 20
        spacing: Theme.gapSm
        Icon {
            anchors.verticalCenter: parent.verticalCenter
            glyph: root.glyph
            size: 14
            color: Theme.accent
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.label
            color: Theme.textMuted
            font: Theme.body
        }
    }

    Text {
        id: valueText
        x: labelRow.x
        y: labelRow.y + labelRow.height + 10
        height: 60
        verticalAlignment: Text.AlignVCenter
        text: root.value
        color: Theme.text
        font: Theme.kpiValue
    }
    Text {
        visible: root.unit.length > 0
        x: valueText.x + valueText.implicitWidth + Theme.space2
        y: valueText.y + valueText.baselineOffset - baselineOffset
        text: root.unit
        color: Theme.textMuted
        font: Theme.unitLarge
    }

    Row {
        x: labelRow.x
        y: root.height - 1 - 20 - height
        height: 18
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.foot
            color: Theme.textMuted
            font: Theme.small
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            visible: root.delta.length > 0
            text: root.delta
            color: root.trend === "down" ? Theme.warn : Theme.ok
            font: Theme.smallStrong
        }
    }
}
