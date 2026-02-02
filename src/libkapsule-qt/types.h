/*
    SPDX-FileCopyrightText: 2024-2026 KDE Community
    SPDX-License-Identifier: LGPL-2.1-or-later
*/

#ifndef KAPSULE_TYPES_H
#define KAPSULE_TYPES_H

#include <QString>
#include <QStringList>
#include <QMetaType>
#include <functional>

#include "kapsule_export.h"

namespace Kapsule {

/**
 * @enum ContainerMode
 * @brief The D-Bus integration mode for a container.
 */
enum class ContainerMode {
    Default,    ///< Host D-Bus session shared with container
    Session,    ///< Container has its own D-Bus session bus
    DbusMux     ///< D-Bus multiplexer for hybrid host/container access
};

/**
 * @enum MessageType
 * @brief Message types for daemon operation progress.
 *
 * These match the Python MessageType enum used by the daemon.
 */
enum class MessageType {
    Info = 0,
    Success = 1,
    Warning = 2,
    Error = 3,
    Dim = 4,
    Hint = 5
};

/**
 * @brief Result of an async operation.
 */
struct KAPSULE_EXPORT OperationResult {
    bool success = false;
    QString error;
};

/**
 * @brief Result of prepareEnter().
 */
struct KAPSULE_EXPORT EnterResult {
    bool success = false;
    QString error;
    QStringList execArgs;
};

/**
 * @brief Progress callback for long-running operations.
 *
 * @param type The message type
 * @param message The message text
 * @param indentLevel Indentation level for hierarchical display
 */
using ProgressHandler = std::function<void(MessageType type, const QString &message, int indentLevel)>;

/**
 * @brief Convert ContainerMode to string.
 */
inline QString containerModeToString(ContainerMode mode)
{
    switch (mode) {
    case ContainerMode::Default:
        return QStringLiteral("default");
    case ContainerMode::Session:
        return QStringLiteral("session");
    case ContainerMode::DbusMux:
        return QStringLiteral("dbus-mux");
    }
    return QStringLiteral("unknown");
}

/**
 * @brief Convert string to ContainerMode.
 */
inline ContainerMode containerModeFromString(const QString &str)
{
    if (str == QStringLiteral("session")) {
        return ContainerMode::Session;
    } else if (str == QStringLiteral("dbus-mux") || str == QStringLiteral("dbusmux")) {
        return ContainerMode::DbusMux;
    }
    return ContainerMode::Default;
}

} // namespace Kapsule

Q_DECLARE_METATYPE(Kapsule::ContainerMode)
Q_DECLARE_METATYPE(Kapsule::MessageType)
Q_DECLARE_METATYPE(Kapsule::OperationResult)
Q_DECLARE_METATYPE(Kapsule::EnterResult)

#endif // KAPSULE_TYPES_H
