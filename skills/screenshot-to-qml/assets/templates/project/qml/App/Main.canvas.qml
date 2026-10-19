import QtQuick
import QtQuick.Layouts
import App.Style

// Fixed design canvas (kiosk / HMI / embedded panel), uniformly scaled to the window.
// Rename to Main.qml when the target screen size is known and fixed.
Window {
    id: window

    readonly property real fitScale: Math.min(width / Theme.designWidth, height / Theme.designHeight)

    width: 1280
    height: 720
    visible: true
    color: Theme.bg
    title: qsTr("{{APP_NAME}}")
    // Kiosk: visibility: Window.FullScreen

    Item {
        id: stage

        width: Theme.designWidth
        height: Theme.designHeight
        scale: window.fitScale
        transformOrigin: Item.TopLeft
        x: (window.width - width * scale) / 2
        y: (window.height - height * scale) / 2

        ColumnLayout {
            anchors.fill: parent
            spacing: 0
            // screen content, laid out with Layouts inside the fixed canvas
        }
    }
}
