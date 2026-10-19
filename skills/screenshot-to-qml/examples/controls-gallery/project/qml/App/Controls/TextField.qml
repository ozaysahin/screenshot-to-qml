import QtQuick
import QtQuick.Templates as T
import App.Style

// Single-line text input with placeholder, error state and a focus ring.
// `glyph` shows a leading icon-font glyph.
T.TextField {
    id: control

    property bool error: false
    property string glyph: ""

    implicitWidth: implicitBackgroundWidth + leftInset + rightInset || Math.max(contentWidth, placeholder.implicitWidth) + leftPadding + rightPadding
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, contentHeight + topPadding + bottomPadding, placeholder.implicitHeight + topPadding + bottomPadding)
    leftPadding: glyph !== "" ? Theme.controlPadding * 2 + font.pixelSize : Theme.controlPadding
    rightPadding: Theme.controlPadding
    verticalAlignment: TextInput.AlignVCenter
    font: Theme.fontInput
    color: Theme.text
    placeholderTextColor: Theme.placeholder
    selectionColor: Theme.focusRing
    selectedTextColor: Theme.text
    opacity: enabled ? 1 : Theme.disabledOpacity
    Accessible.name: placeholderText

    Text {
        id: placeholder

        x: control.leftPadding
        y: control.topPadding
        width: control.width - (control.leftPadding + control.rightPadding)
        height: control.height - (control.topPadding + control.bottomPadding)
        text: control.placeholderText
        font: control.font
        color: control.placeholderTextColor
        verticalAlignment: control.verticalAlignment
        elide: Text.ElideRight
        visible: !control.length && !control.preeditText
        Accessible.ignored: true
    }
    Text {
        x: Theme.controlPadding
        anchors.verticalCenter: parent.verticalCenter
        visible: control.glyph !== ""
        text: control.glyph
        font.family: Theme.fontIcon
        font.pixelSize: control.font.pixelSize
        color: control.error ? Theme.danger : Theme.textMuted
        Accessible.ignored: true
    }

    background: Rectangle {
        id: bg

        implicitWidth: Theme.controlHeight * 6
        implicitHeight: Theme.controlHeight
        radius: Theme.radiusControl
        color: control.error ? Theme.dangerSoft : Theme.surface
        border.width: Theme.borderWidth
        border.color: control.error ? (control.hovered ? Theme.dangerHover : Theme.danger) : control.activeFocus ? Theme.accent : control.hovered ? Theme.borderStrong : Theme.border

        FocusRing {
            visible: control.activeFocus
            baseRadius: bg.radius
            ringColor: control.error ? Theme.alpha(Theme.danger, 0.3) : Theme.focusRing
        }
    }
}
