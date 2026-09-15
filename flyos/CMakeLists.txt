cmake_minimum_required(VERSION 3.16)
project(flyos_host C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

function(flyos_strict_warnings target)
    if(MSVC)
        target_compile_options(${target} PRIVATE /W4 /WX)
    else()
        target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
    endif()
endfunction()

add_library(flyos_core
    fly/network.c
    fly/persistence.c
    display/framebuffer.c
    display/garmin_row_packer.c
    input/mock_input.c
    drivers/hardware_stub.c
)
target_include_directories(flyos_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
flyos_strict_warnings(flyos_core)

add_executable(flyos-host kernel/host_main.c)
target_link_libraries(flyos-host PRIVATE flyos_core)
flyos_strict_warnings(flyos-host)

enable_testing()
add_executable(flyos-tests tests/test_flyos.c)
target_link_libraries(flyos-tests PRIVATE flyos_core)
flyos_strict_warnings(flyos-tests)
add_test(NAME flyos-tests COMMAND flyos-tests)

add_executable(flyos-brain32-tests
    tests/test_brain32.c
    fly/brain32.c
)
target_include_directories(flyos-brain32-tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
flyos_strict_warnings(flyos-brain32-tests)
add_test(NAME flyos-brain32-tests COMMAND flyos-brain32-tests)

add_executable(flyos-brain64-tests
    tests/test_brain64.c
    fly/brain64.c
)
target_include_directories(flyos-brain64-tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
flyos_strict_warnings(flyos-brain64-tests)
add_test(NAME flyos-brain64-tests COMMAND flyos-brain64-tests)

add_executable(flyos-neural-specimen-tests
    tests/test_neural_specimen.c
    display/neural_specimen.c
    fly/brain64.c
)
target_include_directories(flyos-neural-specimen-tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
flyos_strict_warnings(flyos-neural-specimen-tests)
add_test(NAME flyos-neural-specimen-tests COMMAND flyos-neural-specimen-tests)

add_executable(flyos-neural-specimen-preview-role-tests
    tests/test_neural_specimen_preview_roles.c
    display/neural_specimen.c
    fly/brain64.c
)
target_include_directories(flyos-neural-specimen-preview-role-tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_definitions(flyos-neural-specimen-preview-role-tests
    PRIVATE FLY_NEURAL_SPECIMEN_HOST_PREVIEW=1)
flyos_strict_warnings(flyos-neural-specimen-preview-role-tests)
add_test(NAME flyos-neural-specimen-preview-role-tests
    COMMAND flyos-neural-specimen-preview-role-tests)

add_executable(flyos-neural-specimen-preview-exporter
    tools/render_neural_specimen_preview.c display/neural_specimen.c fly/brain64.c)
target_include_directories(flyos-neural-specimen-preview-exporter PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_definitions(flyos-neural-specimen-preview-exporter PRIVATE FLY_NEURAL_SPECIMEN_HOST_PREVIEW=1)
flyos_strict_warnings(flyos-neural-specimen-preview-exporter)

find_package(Python3 COMPONENTS Interpreter REQUIRED)
add_test(NAME flyos-neural-specimen-preview-tests
    COMMAND ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests/test_render_neural_specimen_preview.py
        ${CMAKE_CURRENT_SOURCE_DIR}/tools/render_neural_specimen_preview.py
        $<TARGET_FILE:flyos-neural-specimen-preview-exporter>)

add_executable(flyos-brain-ascii-tests
    tests/test_brain_ascii.c
    display/brain_ascii.c
    fly/brain32.c
)
target_include_directories(flyos-brain-ascii-tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
flyos_strict_warnings(flyos-brain-ascii-tests)
add_test(NAME flyos-brain-ascii-tests COMMAND flyos-brain-ascii-tests)
