cmake_minimum_required(VERSION 3.16)

project(ayaz-cluster VERSION 0.1 LANGUAGES CXX)

# Qt 5.15 host (scaffold.py --min-qt 5.15). The qml/ tree is in the Qt 5.15 dialect (versioned
# imports, QtGraphicalEffects; references/target-qt5.md) and is embedded with assets/, i18n/
# and mock/ as one resource; qmlcachegen compiles the QML ahead of time when Qt5QuickCompiler
# is installed (faster start-up on a board).
set(S2Q_PROFILE "embedded-gpu" CACHE STRING "desktop, embedded-gpu or embedded-sw")
set(S2Q_PROJECT_ROOT "${CMAKE_CURRENT_SOURCE_DIR}" CACHE PATH "project root with qml/ and assets/")
option(S2Q_QMLCACHEGEN "compile QML ahead of time (Qt5QuickCompiler)" ON)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt5 5.15 REQUIRED COMPONENTS Gui Qml Quick)
find_package(Qt5QuickCompiler QUIET)
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")
include(S2qQml5)

# :/qml/... (import path qrc:/qml), :/assets/..., :/i18n/*.qm, :/mock/... — the same relative
# layout as on disk, so relative URLs in QML resolve the same way in the check loop
s2q_write_qrc(s2q_qrc PROJECT_ROOT "${S2Q_PROJECT_ROOT}")
if(S2Q_QMLCACHEGEN AND Qt5QuickCompiler_FOUND)
    qtquick_compiler_add_resources(s2q_resources "${s2q_qrc}")
else()
    qt5_add_resources(s2q_resources "${s2q_qrc}")
endif()

add_executable(app WIN32 MACOSX_BUNDLE src/main.cpp ${s2q_resources})
set_target_properties(app PROPERTIES OUTPUT_NAME "ayaz-cluster")
target_compile_definitions(app PRIVATE
    APP_NAME="Ayaz Cluster"
    APP_ORG=""
    APP_PROFILE="${S2Q_PROFILE}")
target_link_libraries(app PRIVATE Qt5::Gui Qt5::Qml Qt5::Quick)

# Qt 5 has no CMake deploy step: on a board the app uses the image's Qt (Yocto, Buildroot,
# a distro); for a desktop bundle run windeployqt / macdeployqt --qmldir qml on the installed
# binary (deploy.py does it when the tool is in the Qt prefix).
include(GNUInstallDirs)
install(TARGETS app
    BUNDLE DESTINATION .
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
