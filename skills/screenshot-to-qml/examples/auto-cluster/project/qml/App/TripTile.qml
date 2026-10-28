import QtQuick 2.15
import App.Style 1.0

// Trip computer tile: uppercase label, big value with its unit on the same baseline.
Card {
    id: root

    property string label
    property string value
    property string unit

    implicitWidth: Theme.tileWidth
    implicitHeight: Theme.tileHeight
    Accessible.role: Accessible.StaticText
    Accessible.name: label + " " + value + " " + unit

    Text {
        id: labelText

        x: 1 + Theme.space4 + 2
        y: 1 + Theme.space4
        height: Theme.lhTileLabel
        verticalAlignment: Text.AlignVCenter
        text: root.label
        font: Theme.tileLabel
        color: Theme.muted
    }

    Text {
        id: valueText

        x: labelText.x
        y: labelText.y + labelText.height + 10
        height: Theme.lhTileValue
        verticalAlignment: Text.AlignVCenter
        text: root.value
        font: Theme.tileValue
        color: Theme.text
    }

    Text {
        x: valueText.x + valueText.implicitWidth + Theme.space1 + 2
        y: valueText.y + valueText.baselineOffset - baselineOffset
        text: root.unit
        font: Theme.unit
        color: Theme.muted
    }
}
