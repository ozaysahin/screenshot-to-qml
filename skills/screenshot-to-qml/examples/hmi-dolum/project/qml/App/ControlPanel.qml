pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import App.Style
import App.Controls

// Operating mode, target speed and run controls.
Panel {
    id: root

    glyph: Icons.sliders
    title: qsTr("Çalışma Modu")

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        SegmentedControl {
            Layout.fillWidth: true
            options: MockData.modes
            currentIndex: 0
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 28
            Layout.preferredHeight: 31      // line box of the 22 px value (line-height 1.4)
            Text {
                Layout.alignment: Qt.AlignBaseline
                text: qsTr("Hedef Hat Hızı")
                color: Theme.textMuted
                font: Theme.body
            }
            Item {
                Layout.fillWidth: true
            }
            Text {
                Layout.alignment: Qt.AlignBaseline
                text: Number(speed.value).toLocaleString(Qt.locale("tr_TR"), "f", 0)
                color: Theme.text
                font: Theme.sliderValue
            }
            Text {
                Layout.alignment: Qt.AlignBaseline
                Layout.leftMargin: 6 - parent.spacing
                text: qsTr("şişe/dk")
                color: Theme.textMuted
                font: Theme.mono14
            }
        }

        ValueSlider {
            id: speed
            Layout.fillWidth: true
            Layout.topMargin: 14
            from: 0
            to: MockData.speedMax
            stepSize: 50
            value: MockData.speedTarget
            Accessible.name: qsTr("Hedef hat hızı")
        }

        // Scale labels spread edge to edge (CSS justify-content: space-between)
        Item {
            id: speedScale
            readonly property var labels: ["0", "500", "1.000", "1.500", "2.000"]
            Layout.fillWidth: true
            Layout.topMargin: Theme.space2
            Layout.preferredHeight: 17
            Row {
                id: scaleRow
                width: parent.width
                spacing: (width - scaleMetrics.total) / (speedScale.labels.length - 1)
                Repeater {
                    model: speedScale.labels
                    delegate: Text {
                        required property string modelData
                        text: modelData
                        color: Theme.textDim
                        font: Theme.mono12
                    }
                }
            }
            // sum of label widths, needed for space-between spacing
            QtObject {
                id: scaleMetrics
                readonly property real total: {
                    let sum = 0;
                    for (let i = 0; i < scaleRow.children.length; ++i)
                        sum += scaleRow.children[i].implicitWidth || 0;
                    return sum;
                }
            }
        }

        Item {
            Layout.fillHeight: true
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: Theme.space4
            rowSpacing: Theme.space4

            TouchButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                variant: "success"
                glyph: Icons.play
                text: qsTr("BAŞLAT")
                enabled: false          // line is already running
            }
            TouchButton {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                variant: "warningOutline"
                glyph: Icons.pause
                text: qsTr("DURAKLAT")
            }
            TouchButton {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                Layout.preferredHeight: Theme.emergencyButtonHeight
                variant: "danger"
                glyph: Icons.hand
                glyphSize: 28
                font: Theme.emergency
                text: qsTr("ACİL DURDUR")
            }
        }
    }
}
