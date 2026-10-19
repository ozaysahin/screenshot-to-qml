import QtQuick
import QtQuick.Templates as T
import App.Style

// Underlined tab strip; fill it with TabButtons and bind a StackLayout to currentIndex.
T.TabBar {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, contentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, contentHeight + topPadding + bottomPadding)
    spacing: Theme.controlSpacing

    contentItem: ListView {
        model: control.contentModel
        currentIndex: control.currentIndex
        spacing: control.spacing
        orientation: ListView.Horizontal
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.AutoFlickIfNeeded
        snapMode: ListView.SnapToItem
        highlightMoveDuration: Theme.motionFast
        highlightResizeDuration: Theme.motionFast
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: Theme.controlHeight
        preferredHighlightEnd: width - Theme.controlHeight

        highlight: Item {
            z: 2

            Rectangle {
                y: parent.height - height
                width: parent.width
                height: Math.max(2, Theme.focusRingWidth - 1)
                color: Theme.accent
            }
        }
    }

    background: Item {
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: Theme.borderWidth
            color: Theme.border
        }
    }
}
