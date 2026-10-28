import QtQuick 2.15
import App.Style 1.0
import App.Controls 1.0

// Warning lights from MockData.telltales: lit in their tone, otherwise dim.
Row {
    spacing: Theme.telltaleGap

    Repeater {
        model: MockData.telltales

        SvgIcon {
            required property var modelData

            width: Theme.telltale
            height: Theme.telltale
            source: Qt.resolvedUrl("../../assets/icons/" + modelData.icon + ".svg")
            color: !modelData.on ? Theme.dim : modelData.tone === "ok" ? Theme.ok : modelData.tone === "warn" ? Theme.warn : Theme.danger
            Accessible.role: Accessible.Indicator
            Accessible.name: modelData.icon + (modelData.on ? " on" : " off")
        }
    }
}
