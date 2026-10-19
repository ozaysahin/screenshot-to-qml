import QtQuick
import QtQuick.Templates as T
import App.Style

// Number stepper: − value +. Arrow keys and the buttons change the value. The value field
// (contentItem) is the single Tab stop; Up/Down reach the SpinBox from it.
T.SpinBox {
    id: control

    readonly property int buttonSize: compact ? Theme.controlHeightSm : Theme.controlHeight
    property bool compact: false

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, contentItem.implicitWidth + 2 * buttonSize)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, buttonSize)
    leftPadding: buttonSize
    rightPadding: buttonSize
    font: Theme.fontControl
    focusPolicy: Qt.NoFocus
    opacity: enabled ? 1 : Theme.disabledOpacity

    validator: IntValidator {
        locale: control.locale.name
        bottom: Math.min(control.from, control.to)
        top: Math.max(control.from, control.to)
    }

    contentItem: TextInput {
        text: control.displayText
        font: control.font
        color: Theme.text
        selectionColor: Theme.focusRing
        selectedTextColor: Theme.text
        horizontalAlignment: Qt.AlignHCenter
        verticalAlignment: Qt.AlignVCenter
        readOnly: !control.editable
        activeFocusOnTab: true
        validator: control.validator
        inputMethodHints: Qt.ImhFormattedNumbersOnly
    }

    up.indicator: Rectangle {
        x: control.mirrored ? 0 : control.width - width
        implicitWidth: control.buttonSize
        implicitHeight: control.buttonSize
        height: control.height
        radius: Theme.radiusControl
        color: control.up.pressed ? Theme.surfacePressed : control.up.hovered ? Theme.surfaceHover : "transparent"

        Rectangle {
            anchors.centerIn: parent
            width: control.font.pixelSize * 0.8
            height: Math.max(1.5, control.font.pixelSize / 9)
            color: control.value < control.to ? Theme.text : Theme.placeholder
        }
        Rectangle {
            anchors.centerIn: parent
            width: Math.max(1.5, control.font.pixelSize / 9)
            height: control.font.pixelSize * 0.8
            color: control.value < control.to ? Theme.text : Theme.placeholder
        }
    }

    down.indicator: Rectangle {
        x: control.mirrored ? parent.width - width : 0
        implicitWidth: control.buttonSize
        implicitHeight: control.buttonSize
        height: control.height
        radius: Theme.radiusControl
        color: control.down.pressed ? Theme.surfacePressed : control.down.hovered ? Theme.surfaceHover : "transparent"

        Rectangle {
            anchors.centerIn: parent
            width: control.font.pixelSize * 0.8
            height: Math.max(1.5, control.font.pixelSize / 9)
            color: control.value > control.from ? Theme.text : Theme.placeholder
        }
    }

    background: Rectangle {
        id: bg

        implicitWidth: control.buttonSize * 3.5
        radius: Theme.radiusControl
        color: Theme.surface
        border.width: Theme.borderWidth
        border.color: control.hovered ? Theme.borderStrong : Theme.border

        FocusRing {
            visible: control.activeFocus
            baseRadius: bg.radius
        }
    }
}
