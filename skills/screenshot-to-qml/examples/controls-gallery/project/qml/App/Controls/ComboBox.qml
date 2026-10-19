pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Shapes
import QtQuick.Templates as T
import App.Style

// Drop-down list (not editable). Works with string lists and models (set textRole).
T.ComboBox {
    id: control

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding, implicitIndicatorHeight + topPadding + bottomPadding)
    leftPadding: Theme.controlPadding
    rightPadding: Theme.controlPadding * 2 + font.pixelSize / 2
    font: Theme.fontInput
    focusPolicy: Qt.StrongFocus
    opacity: enabled ? 1 : Theme.disabledOpacity

    delegate: T.ItemDelegate {
        id: row

        required property int index

        width: ListView.view.width
        implicitHeight: Theme.controlHeight
        leftPadding: Theme.controlPadding
        rightPadding: Theme.controlPadding
        text: control.textAt(index)
        font: control.font
        highlighted: control.highlightedIndex === index

        contentItem: Text {
            text: row.text
            font: row.font
            color: control.currentIndex === row.index ? Theme.accent : Theme.text
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            radius: Theme.radiusControl
            color: row.down ? Theme.surfacePressed : row.highlighted || row.hovered ? Theme.surfaceHover : "transparent"
        }
    }

    indicator: Shape {
        x: control.width - width - Theme.controlPadding
        y: (control.height - height) / 2
        width: control.font.pixelSize / 1.4
        height: width / 2
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: Theme.textMuted
            strokeWidth: Math.max(1.5, control.font.pixelSize / 9)
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin

            PathPolyline {
                path: [Qt.point(0, 0), Qt.point(control.indicator.width / 2, control.indicator.height), Qt.point(control.indicator.width, 0)]
            }
        }
    }

    contentItem: Text {
        text: control.displayText
        font: control.font
        color: Theme.text
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        id: bg

        implicitWidth: Theme.controlHeight * 5
        implicitHeight: Theme.controlHeight
        radius: Theme.radiusControl
        color: control.down ? Theme.surfacePressed : Theme.surface
        border.width: Theme.borderWidth
        border.color: control.popup.visible ? Theme.accent : control.hovered ? Theme.borderStrong : Theme.border

        FocusRing {
            visible: control.visualFocus
            baseRadius: bg.radius
        }
    }

    popup: T.Popup {
        y: control.height + Theme.controlSpacing / 2
        width: control.width
        implicitHeight: Math.min(contentItem.implicitHeight + topPadding + bottomPadding, Theme.controlHeight * 8)
        padding: Theme.controlSpacing / 2

        contentItem: ListView {
            implicitHeight: contentHeight
            clip: true
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            boundsBehavior: Flickable.StopAtBounds
        }
        background: Rectangle {
            radius: Theme.radiusControl
            color: Theme.surface
            border.width: Theme.borderWidth
            border.color: Theme.border
        }
    }
}
