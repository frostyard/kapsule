/*
    SPDX-FileCopyrightText: 2024-2026 KDE Community
    SPDX-License-Identifier: LGPL-2.1-or-later
*/

#include "container.h"

#include <QSharedData>

namespace Kapsule {

// ============================================================================
// ContainerData (implicitly shared)
// ============================================================================

class ContainerData : public QSharedData
{
public:
    ContainerData() = default;

    ContainerData(const QString &name, Container::State state,
                  const QString &image, ContainerMode mode,
                  const QDateTime &created)
        : name(name)
        , state(state)
        , image(image)
        , mode(mode)
        , created(created)
    {
    }

    QString name;
    Container::State state = Container::State::Unknown;
    QString image;
    ContainerMode mode = ContainerMode::Default;
    QDateTime created;
};

// ============================================================================
// Container implementation
// ============================================================================

Container::Container()
    : d(new ContainerData)
{
}

Container::Container(const QString &name)
    : d(new ContainerData)
{
    d->name = name;
}

Container::Container(const Container &other) = default;
Container::Container(Container &&other) noexcept = default;
Container::~Container() = default;
Container &Container::operator=(const Container &other) = default;
Container &Container::operator=(Container &&other) noexcept = default;

bool Container::isValid() const
{
    return !d->name.isEmpty();
}

QString Container::name() const
{
    return d->name;
}

Container::State Container::state() const
{
    return d->state;
}

QString Container::image() const
{
    return d->image;
}

ContainerMode Container::mode() const
{
    return d->mode;
}

QDateTime Container::created() const
{
    return d->created;
}

bool Container::isRunning() const
{
    return d->state == State::Running;
}

bool Container::operator==(const Container &other) const
{
    return d->name == other.d->name;
}

bool Container::operator!=(const Container &other) const
{
    return !(*this == other);
}

// ============================================================================
// Factory method for internal use
// ============================================================================

Container Container::fromData(const QString &name, const QString &status,
                               const QString &image, const QString &created,
                               const QString &mode)
{
    Container c;
    c.d->name = name;
    c.d->image = image;
    c.d->mode = containerModeFromString(mode);

    // Parse created timestamp
    c.d->created = QDateTime::fromString(created, Qt::ISODate);

    // Parse status to state
    QString statusLower = status.toLower();
    if (statusLower == QLatin1String("running")) {
        c.d->state = State::Running;
    } else if (statusLower == QLatin1String("stopped")) {
        c.d->state = State::Stopped;
    } else if (statusLower == QLatin1String("starting")) {
        c.d->state = State::Starting;
    } else if (statusLower == QLatin1String("stopping")) {
        c.d->state = State::Stopping;
    } else if (statusLower == QLatin1String("error")) {
        c.d->state = State::Error;
    } else {
        c.d->state = State::Unknown;
    }

    return c;
}

} // namespace Kapsule
