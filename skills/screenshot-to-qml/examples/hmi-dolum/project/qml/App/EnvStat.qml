import QtQuick
import App.Style
import App.Controls

// Small environment readout: label with glyph, big mono value and unit.
Rectangle {
    id: root

    property string glyph
    property string label
    property string value
    property string unit

    implicitHeight: 95
    radius: Theme.radiusMd
    color: Theme.panel2

    Row {
        id: labelRow
        x: Theme.space4
        y: Theme.space4
        height: 18
        spacing: Theme.space2
        Icon {
            anchors.verticalCenter: parent.verticalCenter
            glyph: root.glyph
            size: 13
            color: Theme.textMuted
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.label
            color: Theme.textMuted
            font: Theme.small
        }
    }
    Text {
        id: valueText
        x: Theme.space4
        // CSS line box is 39 px (the baseline-aligned unit grows it); the value's
        // content box starts 4 px below the label row.
        y: labelRow.y + labelRow.height + 4
        text: root.value
        color: Theme.text
        font: Theme.statValue
    }
    Text {
        x: valueText.x + valueText.implicitWidth + Theme.space1
        y: valueText.y + valueText.baselineOffset - baselineOffset
        text: root.unit
        color: Theme.textMuted
        font: Theme.unitMedium
    }
}
