import QtQuick
import QtQuick.Templates as T
import App.Style

// Touch slider: 8 px track, 36 px handle centered on the value position.
T.Slider {
    id: control

    implicitWidth: 300
    implicitHeight: 36
    focusPolicy: Qt.StrongFocus

    background: Item {
        Rectangle {
            id: track
            y: 14
            width: control.width
            height: 8
            radius: height / 2
            color: Theme.panel2
            border.color: Theme.border
            border.width: 1
        }
        Rectangle {
            y: 14
            width: control.visualPosition * control.width
            height: 8
            radius: height / 2
            color: Theme.accent
        }
    }

    handle: Rectangle {
        x: control.visualPosition * control.width - width / 2
        y: 0
        width: 36
        height: 36
        radius: width / 2
        color: Theme.text
        border.color: control.visualFocus ? Theme.white : Theme.accent
        border.width: 6
    }
}
