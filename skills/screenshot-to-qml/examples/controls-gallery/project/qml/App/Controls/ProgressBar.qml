import QtQuick
import QtQuick.Templates as T
import App.Style

// Determinate progress bar. Set Accessible.name to what is progressing.
T.ProgressBar {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding)

    contentItem: Item {
        implicitWidth: Theme.controlHeight * 5
        implicitHeight: Math.max(4, Math.round(Theme.controlHeight / 6))

        Rectangle {
            width: control.visualPosition * parent.width
            height: parent.height
            radius: height / 2
            color: Theme.accent
            visible: !control.indeterminate
        }
    }

    background: Rectangle {
        implicitWidth: Theme.controlHeight * 5
        implicitHeight: Math.max(4, Math.round(Theme.controlHeight / 6))
        y: (control.height - height) / 2
        height: control.contentItem.implicitHeight
        radius: height / 2
        color: Theme.track
    }
}
