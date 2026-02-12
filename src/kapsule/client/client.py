"""Async D-Bus client for the kapsule daemon."""

from __future__ import annotations

import os

from dbus_fast import BusType
from dbus_fast.aio import MessageBus

from .exceptions import DaemonNotRunning

BUS_NAME = "org.frostyard.Kapsule"
OBJ_PATH = "/org/frostyard/Kapsule"
MANAGER_IFACE = "org.frostyard.Kapsule.Manager"


def _default_bus_type() -> BusType:
    val = os.environ.get("KAPSULE_BUS", "system").lower()
    if val == "session":
        return BusType.SESSION
    return BusType.SYSTEM


class KapsuleClient:
    """Async client for the kapsule D-Bus daemon.

    Usage:
        async with KapsuleClient() as client:
            containers = await client.list_containers()

    Set KAPSULE_BUS=session to connect to the session bus.
    """

    def __init__(self, bus_type: BusType | None = None):
        self._bus_type = bus_type or _default_bus_type()
        self._bus: MessageBus | None = None
        self._iface = None

    async def __aenter__(self):
        try:
            self._bus = await MessageBus(
                bus_type=self._bus_type
            ).connect()
        except Exception as e:
            raise DaemonNotRunning() from e

        introspection = await self._bus.introspect(BUS_NAME, OBJ_PATH)
        proxy = self._bus.get_proxy_object(
            BUS_NAME, OBJ_PATH, introspection
        )
        self._iface = proxy.get_interface(MANAGER_IFACE)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._bus:
            self._bus.disconnect()
        return False

    async def list_containers(self) -> list[dict]:
        """List all containers.

        Returns list of dicts with keys: name, status, image, created, mode.
        """
        raw = await self._iface.call_list_containers()
        return [
            {
                "name": c[0],
                "status": c[1],
                "image": c[2],
                "created": c[3],
                "mode": c[4],
            }
            for c in raw
        ]

    async def get_container_info(self, name: str) -> dict:
        """Get info for a single container."""
        raw = await self._iface.call_get_container_info(name)
        return {
            "name": raw[0],
            "status": raw[1],
            "image": raw[2],
            "created": raw[3],
            "mode": raw[4],
        }

    async def create_container(
        self,
        name: str,
        *,
        image: str = "",
        session_mode: bool = False,
        dbus_mux: bool = False,
    ) -> str:
        """Create a container. Returns operation D-Bus path."""
        return await self._iface.call_create_container(
            name, image, session_mode, dbus_mux
        )

    async def delete_container(self, name: str, *, force: bool = False) -> str:
        """Delete a container. Returns operation D-Bus path."""
        return await self._iface.call_delete_container(name, force)

    async def start_container(self, name: str) -> str:
        """Start a container. Returns operation D-Bus path."""
        return await self._iface.call_start_container(name)

    async def stop_container(self, name: str, *, force: bool = False) -> str:
        """Stop a container. Returns operation D-Bus path."""
        return await self._iface.call_stop_container(name, force)

    async def prepare_enter(
        self, container_name: str, command: list[str] | None = None
    ) -> tuple[bool, str, list[str]]:
        """Prepare to enter a container.

        Returns (success, message, exec_args).
        """
        result = await self._iface.call_prepare_enter(
            container_name, command or []
        )
        return (result[0], result[1], result[2])

    async def get_config(self) -> dict[str, str]:
        """Get daemon configuration."""
        return await self._iface.call_get_config()

    async def get_version(self) -> str:
        """Get daemon version."""
        return await self._iface.get_version()
