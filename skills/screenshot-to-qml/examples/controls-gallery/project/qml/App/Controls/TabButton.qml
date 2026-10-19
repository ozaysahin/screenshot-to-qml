import QtQuick
import QtQuick.Templates as T
import App.Style

// One tab of a TabBar.
T.TabButton {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding)
    leftPadding: Theme.controlPadding
    rightPadding: Theme.controlPadding
    font: Theme.fontControl
    focusPolicy: Qt.StrongFocus
    opacity: enabled ? 1 : Theme.disabledOpacity

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.checked ? Theme.text : control.hovered ? Theme.text : Theme.textMuted
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        id: bg

        implicitHeight: Theme.controlHeight
        radius: Theme.radiusControl
        color: control.down ? Theme.surfacePressed : control.hovered ? Theme.surfaceHover : "transparent"

        FocusRing {
            visible: control.visualFocus
            baseRadius: bg.radius
        }
    }
}
