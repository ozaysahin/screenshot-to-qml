import QtQuick
import App.Style

// Keyboard-focus outline drawn just outside its parent. Bind `visible` to the control's
// `visualFocus` (keyboard focus only) or, for text inputs, `activeFocus`.
Rectangle {
    property real baseRadius: 0
    property color ringColor: Theme.focusRing

    anchors.fill: parent
    anchors.margins: -(Theme.focusRingWidth + 1)
    radius: baseRadius > 0 ? baseRadius + Theme.focusRingWidth + 1 : 0
    color: "transparent"
    border.width: Theme.focusRingWidth
    border.color: ringColor
    Accessible.ignored: true
}
