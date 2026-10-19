import QtQuick
import QtQuick.Templates as T
import App.Style

// Hover/long-press hint; use as `ToolTip.visible: hovered; ToolTip.text: qsTr("…")` through
// the attached T.ToolTip, or declare one of these.
T.ToolTip {
    id: control

    x: parent ? (parent.width - implicitWidth) / 2 : 0
    y: -implicitHeight - Theme.controlSpacing
    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding)
    margins: Theme.controlSpacing
    padding: Theme.controlSpacing
    font: Theme.fontInput
    delay: 500
    closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutsideParent | T.Popup.CloseOnReleaseOutsideParent

    contentItem: Text {
        text: control.text
        font: control.font
        color: Theme.surface
        wrapMode: Text.Wrap
    }

    background: Rectangle {
        radius: Theme.radiusControl
        color: Theme.text
    }
}
