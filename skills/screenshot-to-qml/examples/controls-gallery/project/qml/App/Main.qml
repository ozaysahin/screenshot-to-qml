pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import App.Style
import App.Controls

// Every control of the kit in its default, checked, error and disabled states.
// The focus ring is shown on "Save" (Tab-focused at start-up).
Window {
    id: window

    width: Theme.designWidth
    height: Theme.designHeight
    visible: true
    color: Theme.bg
    title: qsTr("Controls gallery")

    component Card: Rectangle {
        id: card

        property string title
        default property alias content: body.data

        Layout.fillWidth: true
        Layout.fillHeight: true
        radius: Theme.radiusLg
        color: Theme.surface
        border.width: Theme.borderWidth
        border.color: Theme.border

        ColumnLayout {
            id: body

            anchors.fill: parent
            anchors.margins: Theme.space5
            spacing: Theme.space4

            Text {
                text: card.title
                font: Theme.heading
                color: Theme.text
                Accessible.role: Accessible.Heading
            }
        }
    }

    component Caption: Text {
        font: Theme.caption
        color: Theme.textMuted
    }

    Component.onCompleted: saveButton.forceActiveFocus(Qt.TabFocusReason)

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.space6
        spacing: Theme.space5

        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.space4

            ColumnLayout {
                spacing: Theme.space1

                Text {
                    text: qsTr("Controls gallery")
                    font: Theme.title
                    color: Theme.text
                    Accessible.role: Accessible.Heading
                }
                Caption {
                    text: qsTr("A kit built on QtQuick.Templates; every color and size comes from the Theme.")
                }
            }
            Item {
                Layout.fillWidth: true
            }
            IconButton {
                text: qsTr("Notifications")
                glyph: Icons.bell
            }
            IconButton {
                text: qsTr("Settings")
                glyph: Icons.gear
                checkable: true
                checked: true
            }
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 2
            columnSpacing: Theme.space5
            rowSpacing: Theme.space5

            Card {
                title: qsTr("Buttons")

                Flow {
                    Layout.fillWidth: true
                    spacing: Theme.space3

                    Button {
                        id: saveButton

                        text: qsTr("Save")
                        glyph: Icons.floppyDisk
                    }
                    Button {
                        text: qsTr("Cancel")
                        variant: "secondary"
                    }
                    Button {
                        text: qsTr("Preview")
                        variant: "ghost"
                    }
                    Button {
                        text: qsTr("Delete")
                        variant: "danger"
                        glyph: Icons.trashCan
                    }
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: Theme.space3

                    Button {
                        text: qsTr("New record")
                        glyph: Icons.plus
                        compact: true
                    }
                    Button {
                        text: qsTr("Disabled")
                        enabled: false
                    }
                    Button {
                        text: qsTr("Disabled")
                        variant: "secondary"
                        enabled: false
                    }
                }
                Item {
                    Layout.fillHeight: true
                }
            }

            Card {
                title: qsTr("Text and choice")

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: Theme.space4
                    rowSpacing: Theme.space3

                    TextField {
                        Layout.fillWidth: true
                        placeholderText: qsTr("Search devices…")
                        glyph: Icons.magnifyingGlass
                    }
                    TextField {
                        Layout.fillWidth: true
                        text: qsTr("Lobby Kiosk 02")
                        Accessible.name: qsTr("Device name")
                    }
                    TextField {
                        Layout.fillWidth: true
                        text: qsTr("10.0.0")
                        error: true
                        Accessible.name: qsTr("Server address")
                    }
                    TextField {
                        Layout.fillWidth: true
                        text: qsTr("Read-only")
                        enabled: false
                        Accessible.name: qsTr("Location")
                    }
                    ComboBox {
                        Layout.fillWidth: true
                        model: [qsTr("Turkish"), qsTr("English"), qsTr("German")]
                        Accessible.name: qsTr("Language")
                    }
                    SpinBox {
                        from: 1
                        to: 60
                        value: 15
                        Accessible.name: qsTr("Screen timeout (min)")
                    }
                }
                Caption {
                    text: qsTr("Invalid field: server address incomplete")
                    color: Theme.danger
                }
                Item {
                    Layout.fillHeight: true
                }
            }

            Card {
                title: qsTr("Options")

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space6

                    ColumnLayout {
                        spacing: Theme.space3

                        CheckBox {
                            text: qsTr("Error notifications")
                            checked: true
                        }
                        CheckBox {
                            text: qsTr("Weekly report")
                        }
                        CheckBox {
                            text: qsTr("Some devices")
                            tristate: true
                            checkState: Qt.PartiallyChecked
                        }
                        CheckBox {
                            text: qsTr("Disabled")
                            enabled: false
                        }
                    }
                    ColumnLayout {
                        spacing: Theme.space3

                        RadioButton {
                            text: qsTr("Light theme")
                            checked: true
                        }
                        RadioButton {
                            text: qsTr("Dark theme")
                        }
                        RadioButton {
                            text: qsTr("Follow system")
                        }
                    }
                    ColumnLayout {
                        spacing: Theme.space3

                        Switch {
                            text: qsTr("Automatic updates")
                            checked: true
                        }
                        Switch {
                            text: qsTr("Maintenance mode")
                        }
                        Switch {
                            text: qsTr("Remote access")
                            enabled: false
                        }
                    }
                }
                Item {
                    Layout.fillHeight: true
                }
            }

            Card {
                title: qsTr("Values and navigation")

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space4

                    Caption {
                        text: qsTr("Brightness")
                    }
                    Slider {
                        Layout.fillWidth: true
                        value: 0.6
                        Accessible.name: qsTr("Brightness")
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space4

                    Caption {
                        text: qsTr("Sync")
                    }
                    ProgressBar {
                        Layout.fillWidth: true
                        value: 0.42
                        Accessible.name: qsTr("Sync")
                    }
                }
                SegmentedControl {
                    model: [qsTr("Day"), qsTr("Week"), qsTr("Month")]
                    currentIndex: 1
                    Accessible.name: qsTr("Range")
                }
                TabBar {
                    Layout.fillWidth: true

                    TabButton {
                        text: qsTr("General")
                    }
                    TabButton {
                        text: qsTr("Network")
                    }
                    TabButton {
                        text: qsTr("Security")
                    }
                }
                Item {
                    Layout.fillHeight: true
                }
            }
        }
    }
}
