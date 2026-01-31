"""Kapsule D-Bus daemon.

Provides D-Bus proxy for container session buses with host service fallback.
"""

__version__ = "0.1.0"

from .dbus_proxy import DBusProxy, NameLocation
from .service import KapsuleService, ProxyManager

__all__ = [
    "DBusProxy",
    "KapsuleService",
    "NameLocation",
    "ProxyManager",
    "__version__",
]
