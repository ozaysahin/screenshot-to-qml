import QtQuick
import QtQuick.Layouts
import App.Style

// Resizable desktop window: Layouts reflow; nothing is scaled.
// Rename to Main.qml for normal desktop apps.
Window {
    id: window

    width: Theme.designWidth
    height: Theme.designHeight
    minimumWidth: 960
    minimumHeight: 600
    visible: true
    color: Theme.bg
    title: qsTr("{{APP_NAME}}")

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        // screen content
    }
}
