import QtQuick
import QtQuick.Templates as T
import App.Style

// Horizontal slider. The handle is centered on the value (as CSS sliders draw it), so the
// control keeps half a handle of padding on each side. Set Accessible.name to what it controls.
T.Slider {
    id: control

    readonly property int handleSize: Math.round(Theme.controlHeight * 0.5)
    readonly property int trackHeight: Math.max(4, Math.round(Theme.controlHeight / 10))

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitHandleWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitHandleHeight + topPadding + bottomPadding)
    leftPadding: handleSize / 2
    rightPadding: handleSize / 2
    focusPolicy: Qt.StrongFocus
    opacity: enabled ? 1 : Theme.disabledOpacity

    background: Rectangle {
        x: control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        implicitWidth: Theme.controlHeight * 5
        implicitHeight: control.trackHeight
        width: control.availableWidth
        height: implicitHeight
        radius: height / 2
        color: Theme.track

        Rectangle {
            width: control.visualPosition * parent.width
            height: parent.height
            radius: height / 2
            color: control.pressed ? Theme.accentPressed : Theme.accent
        }
    }

    handle: Rectangle {
        id: knob

        x: control.leftPadding + control.visualPosition * control.availableWidth - width / 2
        y: control.topPadding + (control.availableHeight - height) / 2
        implicitWidth: control.handleSize
        implicitHeight: control.handleSize
        radius: width / 2
        color: Theme.knob
        border.width: Math.max(2, Math.round(control.handleSize / 10))
        border.color: control.pressed ? Theme.accentPressed : control.hovered ? Theme.accentHover : Theme.accent

        FocusRing {
            visible: control.visualFocus
            baseRadius: knob.radius
        }
    }
}
