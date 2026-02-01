"""Kapsule D-Bus daemon.

Provides container management services over D-Bus.
"""

__version__ = "0.1.0"

from .service import KapsuleService, KapsuleManagerInterface
from .container_service import ContainerService
from .operations import (
    MessageType,
    OperationError,
    OperationReporter,
    operation,
)

__all__ = [
    "ContainerService",
    "KapsuleManagerInterface",
    "KapsuleService",
    "MessageType",
    "OperationError",
    "OperationReporter",
    "__version__",
    "operation",
]
