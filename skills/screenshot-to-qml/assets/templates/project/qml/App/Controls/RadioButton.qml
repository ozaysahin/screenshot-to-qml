import QtQuick
import QtQuick.Templates as T
import App.Style

// Radio button; put the options of one choice in a T.ButtonGroup (or one parent item,
// which makes them auto-exclusive).
T.RadioButton {
    id: control

    readonly property int dotSize: Math.round(Theme.controlHeight * 0.45)

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding, implicitIndicatorHeight + topPadding + bottomPadding)
    padding: 0
    spacing: Theme.controlSpacing
    font: Theme.fontInput
    focusPolicy: Qt.StrongFocus
    opacity: enabled ? 1 : Theme.disabledOpacity

    indicator: Rectangle {
        id: ring

        implicitWidth: control.dotSize
        implicitHeight: control.dotSize
        x: control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        radius: width / 2
        color: control.down ? Theme.surfacePressed : Theme.surface
        border.width: control.checked ? Math.round(ring.width * 0.3) : Theme.borderWidth
        border.color: control.checked ? (control.hovered ? Theme.accentHover : Theme.accent) : control.hovered ? Theme.accent : Theme.borderStrong

        FocusRing {
            visible: control.visualFocus
            baseRadius: ring.radius
        }
    }

    contentItem: Text {
        leftPadding: control.text !== "" ? control.indicator.width + control.spacing : control.indicator.width
        text: control.text
        font: control.font
        color: Theme.text
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
