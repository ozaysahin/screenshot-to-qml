pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Templates as T
import App.Style

// A few exclusive options side by side. `model` is a list of labels; read `currentIndex`,
// react to `activated(index)`. Every segment is a checkable button, reachable with Tab.
T.Control {
    id: control

    property var model: []
    property int currentIndex: 0

    signal activated(int index)

    implicitWidth: implicitContentWidth + leftPadding + rightPadding
    implicitHeight: Theme.controlHeight
    padding: Theme.borderWidth + 2
    font: Theme.fontControl
    opacity: enabled ? 1 : Theme.disabledOpacity
    Accessible.role: Accessible.PageTabList

    T.ButtonGroup {
        id: group

        exclusive: true
    }

    contentItem: Row {
        spacing: Theme.borderWidth * 2

        Repeater {
            model: control.model

            delegate: T.Button {
                id: segment

                required property int index
                required property var modelData

                implicitWidth: implicitContentWidth + leftPadding + rightPadding
                height: control.availableHeight
                leftPadding: Theme.controlPadding
                rightPadding: Theme.controlPadding
                text: segment.modelData
                font: control.font
                checkable: true
                checked: control.currentIndex === index
                focusPolicy: Qt.StrongFocus
                T.ButtonGroup.group: group
                Accessible.role: Accessible.PageTab
                onClicked: {
                    control.currentIndex = index;
                    control.activated(index);
                }

                contentItem: Text {
                    text: segment.text
                    font: segment.font
                    color: segment.checked ? Theme.accentInk : Theme.text
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    id: pill

                    radius: Math.max(0, Theme.radiusControl - 2)
                    color: segment.checked ? (segment.down ? Theme.accentPressed : segment.hovered ? Theme.accentHover : Theme.accent) : segment.down ? Theme.surfacePressed : segment.hovered ? Theme.surfaceHover : "transparent"

                    FocusRing {
                        visible: segment.visualFocus
                        baseRadius: pill.radius
                    }
                }
            }
        }
    }

    background: Rectangle {
        radius: Theme.radiusControl
        color: Theme.surface
        border.width: Theme.borderWidth
        border.color: Theme.border
    }
}
