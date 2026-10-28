# S2qQml5.cmake — embed a project's qml/ tree and its files as one Qt 5 resource.
#
# s2q_write_qrc(<out_var> [PROJECT_ROOT <dir>])
#   writes ${CMAKE_BINARY_DIR}/s2q_project.qrc listing every file under <dir>/qml, assets,
#   i18n and mock with its path relative to <dir> as the alias (qrc:/qml/App/Main.qml,
#   qrc:/assets/fonts/…), and sets <out_var> to it. The globs are CONFIGURE_DEPENDS, so a file
#   added later is picked up by the next build. The qrc is rewritten only when its content
#   changes, so an unchanged tree does not rebuild the resource.

include_guard(GLOBAL)

function(s2q_write_qrc out_var)
    cmake_parse_arguments(ARG "" "PROJECT_ROOT" "" ${ARGN})
    if(NOT ARG_PROJECT_ROOT)
        set(ARG_PROJECT_ROOT "${CMAKE_CURRENT_SOURCE_DIR}")
    endif()
    get_filename_component(root "${ARG_PROJECT_ROOT}" ABSOLUTE)
    if(NOT EXISTS "${root}/qml")
        message(FATAL_ERROR "s2q: no qml/ folder in ${root}")
    endif()
    set(entries "")
    set(n 0)
    foreach(sub qml assets i18n mock)
        if(NOT EXISTS "${root}/${sub}")
            continue()
        endif()
        file(GLOB_RECURSE files LIST_DIRECTORIES false CONFIGURE_DEPENDS "${root}/${sub}/*")
        list(FILTER files EXCLUDE REGEX "/\\.gitkeep$|\\.ts$|\\.qmltypes$|\\.qmlproject$|/Main\\.(canvas|responsive)\\.qml$")
        list(SORT files)
        foreach(f IN LISTS files)
            file(RELATIVE_PATH rel "${root}" "${f}")
            string(REPLACE "&" "&amp;" f_xml "${f}")
            string(REPLACE "&" "&amp;" rel_xml "${rel}")
            string(APPEND entries "    <file alias=\"${rel_xml}\">${f_xml}</file>\n")
            math(EXPR n "${n} + 1")
        endforeach()
    endforeach()
    set(qrc "${CMAKE_BINARY_DIR}/s2q_project.qrc")
    file(WRITE "${qrc}.new" "<RCC>\n  <qresource prefix=\"/\">\n${entries}  </qresource>\n</RCC>\n")
    configure_file("${qrc}.new" "${qrc}" COPYONLY)
    set(${out_var} "${qrc}" PARENT_SCOPE)
    message(STATUS "s2q: ${n} files from ${root} embedded (Qt 5.15 resource)")
endfunction()
