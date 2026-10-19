import QtQuick
import QtQuick.Shapes
import QtQuick.Templates as T
import App.Style

// Check box with checked, partially checked (tristate) and disabled states.
T.CheckBox {
    id: control

    readonly property int boxSize: Math.round(Theme.controlHeight * 0.45)
    readonly property bool marked: checkState !== Qt.Unchecked

    implicitWidth: Math.max(implicitBackgroundWidth + leftInset + rightInset, implicitContentWidth + leftPadding + rightPadding)
    implicitHeight: Math.max(implicitBackgroundHeight + topInset + bottomInset, implicitContentHeight + topPadding + bottomPadding, implicitIndicatorHeight + topPadding + bottomPadding)
    padding: 0
    spacing: Theme.controlSpacing
    font: Theme.fontInput
    focusPolicy: Qt.StrongFocus
    opacity: enabled ? 1 : Theme.disabledOpacity

    indicator: Rectangle {
        id: box

        implicitWidth: control.boxSize
        implicitHeight: control.boxSize
        x: control.leftPadding
        y: control.topPadding + (control.availableHeight - height) / 2
        radius: Math.round(Theme.radiusControl / 2)
        color: control.marked ? (control.down ? Theme.accentPressed : control.hovered ? Theme.accentHover : Theme.accent) : control.down ? Theme.surfacePressed : Theme.surface
        border.width: control.marked ? 0 : Theme.borderWidth
        border.color: control.hovered ? Theme.accent : Theme.borderStrong

        Shape {
            anchors.fill: parent
            visible: control.checkState === Qt.Checked
            preferredRendererType: Shape.CurveRenderer

            ShapePath {
                strokeColor: Theme.accentInk
                strokeWidth: Math.max(1.5, box.width / 9)
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin

                PathPolyline {
                    path: [Qt.point(box.width * 0.26, box.height * 0.52), Qt.point(box.width * 0.44, box.height * 0.7), Qt.point(box.width * 0.76, box.height * 0.32)]
                }
            }
        }
        Rectangle {
            anchors.centerIn: parent
            visible: control.checkState === Qt.PartiallyChecked
            width: box.width * 0.5
            height: Math.max(1.5, box.width / 9)
            radius: height / 2
            color: Theme.accentInk
        }
        FocusRing {
            visible: control.visualFocus
            baseRadius: box.radius
        }
    }

    contentItem: Text {
        leftPadding: control.text !== "" ? control.indicator.width + control.spacing : control.indicator.width
        text: control.text
        font: control.font
        color: Theme.text
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
