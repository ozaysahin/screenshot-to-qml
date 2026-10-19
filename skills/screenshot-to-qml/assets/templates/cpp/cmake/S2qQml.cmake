# S2qQml.cmake — build the project's QML modules from their qmldir files.
#
# The qml/ tree is shared with the PySide6 host (main.py): every folder with a qmldir is a
# module, and the qmldir stays the single source of truth for its URI and singletons. This
# helper turns each one into a static library + QML plugin (qt_add_qml_module), so QML is
# compiled ahead of time (qmlcachegen) and the executable carries everything it needs.
#
# Resource layout (relative URLs in QML resolve the same way in both hosts):
#   :/qt/qml/<Module/Path>/...   QML files and resources inside module folders
#   :/qt/assets/...              PROJECT/assets (fonts, images)
#   :/qt/i18n/*.qm               PROJECT/i18n translations
#   :/qt/mock/...                PROJECT/mock (sample data)
#
# s2q_add_qml_modules(<target> [PROJECT_ROOT <dir>])
#   adds every module under <dir>/qml, links their plugins to <target>, embeds the project
#   files above, and writes ${CMAKE_BINARY_DIR}/s2q_qml_plugins.h (Q_IMPORT_QML_PLUGIN lines).

include_guard(GLOBAL)

# files (absolute) whose path starts with one of the prefixes are dropped
function(_s2q_drop_under out_var prefixes)
    set(kept "")
    foreach(f IN LISTS ${out_var})
        set(drop FALSE)
        foreach(p IN LISTS prefixes)
            string(FIND "${f}" "${p}/" pos)
            if(pos EQUAL 0)
                set(drop TRUE)
            endif()
        endforeach()
        if(NOT drop)
            list(APPEND kept "${f}")
        endif()
    endforeach()
    set(${out_var} "${kept}" PARENT_SCOPE)
endfunction()

function(s2q_add_qml_modules target)
    cmake_parse_arguments(ARG "" "PROJECT_ROOT" "" ${ARGN})
    if(NOT ARG_PROJECT_ROOT)
        set(ARG_PROJECT_ROOT "${CMAKE_CURRENT_SOURCE_DIR}")
    endif()
    get_filename_component(root "${ARG_PROJECT_ROOT}" ABSOLUTE)
    set(qml_root "${root}/qml")
    if(NOT EXISTS "${qml_root}")
        message(FATAL_ERROR "s2q: no qml/ folder in ${root}")
    endif()

    # pass 1: modules (folder, URI, singletons)
    file(GLOB_RECURSE qmldirs LIST_DIRECTORIES false "${qml_root}/*qmldir")
    list(FILTER qmldirs INCLUDE REGEX "/qmldir$")
    list(SORT qmldirs)
    set(dirs "")
    set(uris "")
    foreach(qd IN LISTS qmldirs)
        get_filename_component(dir "${qd}" DIRECTORY)
        file(STRINGS "${qd}" lines)
        set(uri "")
        foreach(line IN LISTS lines)
            if(line MATCHES "^module[ \t]+([A-Za-z0-9_.]+)")
                set(uri "${CMAKE_MATCH_1}")
            endif()
        endforeach()
        if(NOT uri)
            message(FATAL_ERROR "s2q: ${qd} has no 'module' line")
        endif()
        list(APPEND dirs "${dir}")
        list(APPEND uris "${uri}")
    endforeach()

    # pass 2: one static QML module per folder
    set(imports "#pragma once\n#include <QtQml/qqmlextensionplugin.h>\n")
    set(module_targets "")
    list(LENGTH dirs n)
    if(n EQUAL 0)
        message(FATAL_ERROR "s2q: no qmldir under ${qml_root}")
    endif()
    math(EXPR last "${n} - 1")
    foreach(i RANGE ${last})
        list(GET dirs ${i} dir)
        list(GET uris ${i} uri)
        set(nested "")
        foreach(other IN LISTS dirs)
            string(FIND "${other}" "${dir}/" pos)
            if(pos EQUAL 0)
                list(APPEND nested "${other}")
            endif()
        endforeach()

        # QML/JS of this folder and of its plain subfolders (`import "parts"`), not of nested modules
        file(GLOB_RECURSE qml_files LIST_DIRECTORIES false "${dir}/*.qml" "${dir}/*.js" "${dir}/*.mjs")
        list(FILTER qml_files EXCLUDE REGEX "/Main\\.(canvas|responsive)\\.qml$")
        _s2q_drop_under(qml_files "${nested}")
        file(GLOB_RECURSE res LIST_DIRECTORIES false "${dir}/*")
        list(FILTER res EXCLUDE REGEX "\\.(qml|js|mjs)$|/qmldir$|/\\.gitkeep$|\\.qmlproject$|\\.qmltypes$")
        _s2q_drop_under(res "${nested}")

        # singletons come from the qmldir; local modules this one imports become dependencies
        file(STRINGS "${dir}/qmldir" lines)
        set(singletons "")
        foreach(line IN LISTS lines)
            # "singleton Theme 1.0 Theme.qml" or, without a version, "singleton Theme Theme.qml"
            if(line MATCHES "^singleton[ \t]+[A-Za-z0-9_]+[ \t]+([0-9]+\\.[0-9]+[ \t]+)?([^ \t]+)")
                list(APPEND singletons "${dir}/${CMAKE_MATCH_2}")
            endif()
        endforeach()
        set(deps "")
        foreach(f IN LISTS qml_files)
            file(STRINGS "${f}" import_lines REGEX "^[ \t]*import[ \t]+[A-Za-z]")
            foreach(line IN LISTS import_lines)
                if(line MATCHES "^[ \t]*import[ \t]+([A-Za-z0-9_.]+)")
                    list(FIND uris "${CMAKE_MATCH_1}" k)
                    if(k GREATER -1 AND NOT CMAKE_MATCH_1 STREQUAL uri)
                        list(APPEND deps "${CMAKE_MATCH_1}")
                    endif()
                endif()
            endforeach()
        endforeach()
        list(REMOVE_DUPLICATES deps)

        foreach(f IN LISTS qml_files res)
            file(RELATIVE_PATH rel "${dir}" "${f}")
            set_source_files_properties("${f}" PROPERTIES QT_RESOURCE_ALIAS "${rel}")
            if(rel MATCHES "/" AND f MATCHES "\\.qml$")
                # a file in a plain subfolder is reached by a directory import, not as a module type
                set_source_files_properties("${f}" PROPERTIES QT_QML_INTERNAL_TYPE TRUE)
            endif()
        endforeach()
        if(singletons)
            set_source_files_properties(${singletons} PROPERTIES QT_QML_SINGLETON_TYPE TRUE)
        endif()

        string(REPLACE "." "_" id "${uri}")
        string(REPLACE "." "/" uri_path "${uri}")
        set(lib "s2q_${id}")
        qt_add_library(${lib} STATIC)
        set(dep_args "")
        if(deps)
            set(dep_args DEPENDENCIES ${deps})
        endif()
        qt_add_qml_module(${lib}
            URI ${uri}
            VERSION 1.0
            CLASS_NAME ${id}Plugin
            OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/qml/${uri_path}"
            IMPORT_PATH "${CMAKE_BINARY_DIR}/qml"
            ${dep_args}
            QML_FILES ${qml_files}
            RESOURCES ${res}
        )
        foreach(d IN LISTS deps)
            string(REPLACE "." "_" did "${d}")
            add_dependencies(${lib} s2q_${did})
        endforeach()
        target_link_libraries(${target} PRIVATE ${lib}plugin)
        list(APPEND module_targets ${lib})
        string(APPEND imports "Q_IMPORT_QML_PLUGIN(${id}Plugin)\n")
    endforeach()

    # project assets, translations and mock data at :/qt/<same relative path>
    set(extra "")
    foreach(sub assets i18n mock)
        if(EXISTS "${root}/${sub}")
            file(GLOB_RECURSE files LIST_DIRECTORIES false "${root}/${sub}/*")
            list(FILTER files EXCLUDE REGEX "/\\.gitkeep$|\\.ts$")
            list(APPEND extra ${files})
        endif()
    endforeach()
    if(extra)
        qt_add_resources(${target} s2q_project_files PREFIX "/qt" BASE "${root}" FILES ${extra})
    endif()

    file(CONFIGURE OUTPUT "${CMAKE_BINARY_DIR}/s2q_qml_plugins.h" CONTENT "${imports}")
    target_include_directories(${target} PRIVATE "${CMAKE_BINARY_DIR}")
    set(S2Q_QML_MODULE_TARGETS ${module_targets} PARENT_SCOPE)
    message(STATUS "s2q: ${n} QML modules (${uris}) from ${qml_root}")
endfunction()
