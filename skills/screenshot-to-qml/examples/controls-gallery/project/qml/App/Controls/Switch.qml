import QtQuick
import QtQuick.Templates as T
import App.Style

// On/off switch; the knob slides with `checked`.
T.Switch {
    id: control

    readonly property int trackHeight: Math.round(Theme.controlHeight * 0.55)

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding, implicitIndicatorHeight + topPadding + bottomPadding)
    padding: 0
    spacing: Theme.controlSpacing
    font: Theme.fontInput
    focusPolicy: Qt.StrongFocus
    opacity: enabled ? 1 : Theme.disabledOpacity

    indicator: Rectangle {
        id: track

        implicitWidth: Math.round(control.trackHeight * 1.8)
        implicitHeight: control.trackHeight
        x: control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        radius: height / 2
        color: control.checked ? (control.down ? Theme.accentPressed : control.hovered ? Theme.accentHover : Theme.accent) : control.down ? Theme.textMuted : control.hovered ? Theme.placeholder : Theme.track

        Rectangle {
            readonly property real inset: Math.max(2, track.height / 10)

            x: control.checked ? track.width - width - inset : inset
            y: inset
            width: track.height - 2 * inset
            height: width
            radius: width / 2
            color: Theme.knob

            Behavior on x {
                enabled: !control.down
                NumberAnimation {
                    duration: Theme.motionFast
                }
            }
        }
        FocusRing {
            visible: control.visualFocus
            baseRadius: track.radius
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
