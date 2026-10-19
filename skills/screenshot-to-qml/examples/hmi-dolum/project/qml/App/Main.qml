pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import App.Style

// Fixed 1920x1080 kiosk canvas, uniformly scaled to the window.
// Inside the canvas everything is laid out with Qt Quick Layouts.
Window {
    id: window

    width: 1280
    height: 720
    visible: true
    color: Theme.bg
    title: MockData.station
    // Kiosk: visibility: Window.FullScreen

    readonly property real fitScale: Math.min(width / Theme.designWidth, height / Theme.designHeight)

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

            TopBar {
                Layout.fillWidth: true
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.margins: Theme.space5
                Layout.leftMargin: Theme.space6
                Layout.rightMargin: Theme.space6
                spacing: Theme.space5

                TankPanel {
                    Layout.preferredWidth: Theme.sideColumnWidth
                    Layout.fillHeight: true
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: Theme.space5

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: Theme.space5
                        rowSpacing: Theme.space5
                        Repeater {
                            model: MockData.kpis
                            delegate: KpiCard {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                glyph: modelData.glyph
                                label: modelData.label
                                value: modelData.value
                                unit: modelData.unit
                                foot: modelData.foot
                                delta: modelData.delta
                                trend: modelData.trend
                            }
                        }
                    }
                    PressureCard {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                    }
                }

                ColumnLayout {
                    Layout.preferredWidth: Theme.sideColumnWidth
                    Layout.fillWidth: false
                    Layout.fillHeight: true
                    spacing: Theme.space5
                    AlarmPanel {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 380
                    }
                    ControlPanel {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                    }
                }
            }

            StatusBar {
                Layout.fillWidth: true
            }
        }
    }
}
