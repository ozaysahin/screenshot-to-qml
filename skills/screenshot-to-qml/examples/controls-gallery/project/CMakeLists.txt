cmake_minimum_required(VERSION 3.22)

project(controls-gallery VERSION 0.1 LANGUAGES CXX)

# Screen profile from the design spec: desktop | embedded-gpu | embedded-sw.
# embedded-sw makes the software scene graph the default (no GPU, no shader effects).
set(S2Q_PROFILE "desktop" CACHE STRING "desktop, embedded-gpu or embedded-sw")
# The folder holding qml/, assets/, i18n/ (shared with the PySide6 host, main.py).
set(S2Q_PROJECT_ROOT "${CMAKE_CURRENT_SOURCE_DIR}" CACHE PATH "project root with qml/ and assets/")

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt6 6.8 REQUIRED COMPONENTS Gui Qml Quick)
qt_standard_project_setup(REQUIRES 6.8)
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(S2qQml)

qt_add_executable(app src/main.cpp)
set_target_properties(app PROPERTIES
    OUTPUT_NAME "controls-gallery"
    MACOSX_BUNDLE TRUE          # macOS: an .app (the deploy script only bundles apps)
    WIN32_EXECUTABLE TRUE)      # Windows: no console window
target_compile_definitions(app PRIVATE
    APP_NAME="Controls Gallery"
    APP_ORG="screenshot-to-qml"
    APP_PROFILE="${S2Q_PROFILE}")
target_link_libraries(app PRIVATE Qt6::Gui Qt6::Qml Qt6::Quick)

# every qml/**/qmldir becomes a compiled QML module; assets, i18n and mock are embedded
s2q_add_qml_modules(app PROJECT_ROOT "${S2Q_PROJECT_ROOT}")

# Qt from the OS (a distro, or a Yocto/Buildroot image: prefix /usr) comes with the system, so
# the app ships alone. Qt from an SDK (online installer, aqt) is bundled by `cmake --install`.
if(QT6_INSTALL_PREFIX STREQUAL "/usr" OR CMAKE_CROSSCOMPILING)
    set(s2q_bundle_default OFF)
else()
    set(s2q_bundle_default ON)
endif()
option(S2Q_DEPLOY_QT "copy Qt libraries, plugins and QML modules on cmake --install" ${s2q_bundle_default})

get_target_property(s2q_qt_core_type Qt6::Core TYPE)
if(s2q_qt_core_type STREQUAL "SHARED_LIBRARY" AND NOT S2Q_DEPLOY_QT)
    # a shared Qt loads its QML plugins at run time: the static-import scan is not needed
    set_target_properties(app PROPERTIES QT_QML_MODULE_NO_IMPORT_SCAN ON)
endif()

include(GNUInstallDirs)
install(TARGETS app
    BUNDLE DESTINATION .
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
if(S2Q_DEPLOY_QT)
    qt_generate_deploy_qml_app_script(
        TARGET app
        OUTPUT_SCRIPT deploy_script
        NO_TRANSLATIONS
        NO_UNSUPPORTED_PLATFORM_ERROR)
    install(SCRIPT ${deploy_script})
endif()
