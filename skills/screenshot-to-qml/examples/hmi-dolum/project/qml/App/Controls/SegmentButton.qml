import QtQuick
import QtQuick.Templates as T
import App.Style

// One option of a SegmentedControl.
T.Button {
    id: control

    checkable: true
    implicitHeight: 52
    focusPolicy: Qt.StrongFocus
    font: checked ? Theme.segmentSelected : Theme.segment

    background: Rectangle {
        radius: Theme.radiusSm
        color: control.checked ? (control.down ? Qt.darker(Theme.accent, 1.15) : Theme.accent) : control.down ? Theme.alpha(Theme.text, 0.08) : "transparent"
        border.color: control.visualFocus ? Theme.text : "transparent"
        border.width: control.visualFocus ? 2 : 0
    }
    contentItem: Text {
        text: control.text
        font: control.font
        color: control.checked ? Theme.accentInk : Theme.textMuted
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
