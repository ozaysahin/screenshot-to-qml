import QtQuick
import QtQuick.Layouts
import App.Style

// Card with a header row (glyph, title, aside text, trailing slot) and a body.
// Children go into the body; `trailing` children go to the right end of the header.
Rectangle {
    id: root

    property string glyph
    property string title
    property string aside
    property int padding: Theme.space5
    default property alias content: body.data
    property alias trailing: trailingSlot.data

    color: Theme.panel
    radius: Theme.radiusLg
    border.color: Theme.border
    border.width: 1
    Accessible.role: Accessible.Pane
    Accessible.name: title

    RowLayout {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: root.padding + root.border.width
        height: 24
        spacing: Theme.space3

        Icon {
            glyph: root.glyph
            size: 18
            color: Theme.accent
        }
        Text {
            text: root.title
            color: Theme.text
            font: Theme.heading
            Layout.preferredHeight: 24
            verticalAlignment: Text.AlignVCenter
        }
        Item {
            Layout.fillWidth: true
        }
        Text {
            visible: root.aside.length > 0
            text: root.aside
            color: Theme.textMuted
            font: Theme.small
        }
        Item {
            id: trailingSlot
            implicitWidth: childrenRect.width
            implicitHeight: childrenRect.height
            visible: children.length > 0
        }
    }

    Item {
        id: body
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.leftMargin: root.padding + root.border.width
        anchors.rightMargin: root.padding + root.border.width
        anchors.topMargin: 20
        anchors.bottomMargin: root.padding + root.border.width
    }
}
