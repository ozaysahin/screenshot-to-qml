pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Templates as T
import App.Style

// Exclusive option group (e.g. Otomatik / Manuel / Bakım).
Rectangle {
    id: root

    property var options: []
    property int currentIndex: 0
    signal activated(int index)

    implicitHeight: 62
    radius: Theme.radiusMd
    color: Theme.panel2
    border.color: Theme.border
    border.width: 1
    Accessible.role: Accessible.PageTabList

    T.ButtonGroup {
        id: group
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 4 + root.border.width
        spacing: Theme.space1
        Repeater {
            model: root.options
            delegate: SegmentButton {
                required property string modelData
                required property int index
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                text: modelData
                checked: index === root.currentIndex
                T.ButtonGroup.group: group
                onClicked: {
                    root.currentIndex = index;
                    root.activated(index);
                }
            }
        }
    }
}
