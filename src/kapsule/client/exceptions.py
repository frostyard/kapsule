"""Kapsule client exceptions."""


class KapsuleError(Exception):
    """Base exception for kapsule client errors."""


class DaemonNotRunning(KapsuleError):
    """The kapsule daemon is not running."""

    def __init__(self):
        super().__init__(
            "kapsule daemon is not running. "
            "Start it with: sudo systemctl start kapsule-daemon"
        )


class ContainerNotFound(KapsuleError):
    """The requested container does not exist."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"container not found: {name}")


class ContainerError(KapsuleError):
    """An operation on a container failed."""

    def __init__(self, message: str):
        super().__init__(message)
