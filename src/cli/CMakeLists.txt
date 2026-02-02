# SPDX-FileCopyrightText: 2024-2026 KDE Community
# SPDX-License-Identifier: BSD-3-Clause

# kapsule CLI - C++ command-line interface

add_executable(kapsule-cli
    main.cpp
    output.cpp
)

target_include_directories(kapsule-cli
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(kapsule-cli
    PRIVATE
        Kapsule::KapsuleQt
        Qt6::Core
        QCoro6::Core
)

# Install
install(TARGETS kapsule-cli
    DESTINATION ${KDE_INSTALL_BINDIR}
    RENAME kapsule
)
