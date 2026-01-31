"""D-Bus service implementation for Kapsule.

Provides D-Bus proxy management for container session buses with host fallback.
"""

from __future__ import annotations

import asyncio

from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method, dbus_property, signal
from dbus_fast import BusType, Variant
from dbus_fast.constants import PropertyAccess

from . import __version__
from .dbus_proxy import DBusProxy


class KapsuleManagerInterface(ServiceInterface):
    """org.kde.kapsule.Manager D-Bus interface.

    Provides container D-Bus proxy management over D-Bus.
    """

    def __init__(self, proxy_manager: ProxyManager):
        super().__init__("org.kde.kapsule.Manager")
        self._proxy_manager = proxy_manager
        self._version = __version__

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @dbus_property(access=PropertyAccess.READ)
    def Version(self) -> "s":
        """Daemon version."""
        return self._version

    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------

    @method()
    async def StartProxy(self, container_name: "s", container_bus_address: "s") -> "b":
        """Start a D-Bus proxy for a container.

        Args:
            container_name: Name of the container.
            container_bus_address: D-Bus address for the container's session bus.

        Returns:
            True if proxy started successfully.
        """
        try:
            await self._proxy_manager.start_proxy(container_name, container_bus_address)
            return True
        except Exception as e:
            print(f"Failed to start proxy for {container_name}: {e}")
            return False

    @method()
    async def StopProxy(self, container_name: "s") -> "b":
        """Stop a D-Bus proxy for a container.

        Args:
            container_name: Name of the container.

        Returns:
            True if proxy stopped successfully.
        """
        try:
            await self._proxy_manager.stop_proxy(container_name)
            return True
        except Exception as e:
            print(f"Failed to stop proxy for {container_name}: {e}")
            return False

    @method()
    async def ListProxies(self) -> "a(ssi)":
        """List all running D-Bus proxies.

        Returns:
            Array of structs: (container_name, bus_address, name_count)
        """
        return self._proxy_manager.list_proxies()

    @method()
    async def GetProxyStats(self, container_name: "s") -> "a{sv}":
        """Get statistics for a specific proxy.

        Args:
            container_name: Name of the container.

        Returns:
            Dictionary of stats (local_names, host_names, pending_calls, etc.)
        """
        stats = self._proxy_manager.get_proxy_stats(container_name)
        return {k: Variant("i", v) for k, v in stats.items()}

    # -------------------------------------------------------------------------
    # Signals
    # -------------------------------------------------------------------------

    @signal()
    def ProxyStarted(self, container_name: str) -> "s":
        """Emitted when a proxy starts."""
        return container_name

    @signal()
    def ProxyStopped(self, container_name: str) -> "s":
        """Emitted when a proxy stops."""
        return container_name


class ProxyManager:
    """Manages D-Bus proxies for multiple containers."""

    def __init__(self, host_bus_address: str | None = None):
        """Initialize the proxy manager.

        Args:
            host_bus_address: D-Bus address for host session bus.
                If None, uses DBUS_SESSION_BUS_ADDRESS.
        """
        self._host_bus_address = host_bus_address
        self._proxies: dict[str, DBusProxy] = {}
        self._proxy_tasks: dict[str, asyncio.Task] = {}

    async def start_proxy(
        self,
        container_name: str,
        container_bus_address: str,
    ) -> None:
        """Start a D-Bus proxy for a container.

        Args:
            container_name: Name of the container.
            container_bus_address: D-Bus address for the container's session bus.
        """
        if container_name in self._proxies:
            raise ValueError(f"Proxy already running for {container_name}")

        proxy = DBusProxy(
            container_bus_address=container_bus_address,
            host_bus_address=self._host_bus_address,
        )
        await proxy.start()

        self._proxies[container_name] = proxy
        self._proxy_tasks[container_name] = asyncio.create_task(
            proxy.run(),
            name=f"proxy-{container_name}",
        )

    async def stop_proxy(self, container_name: str) -> None:
        """Stop a D-Bus proxy.

        Args:
            container_name: Name of the container.
        """
        if container_name not in self._proxies:
            return

        proxy = self._proxies.pop(container_name)
        task = self._proxy_tasks.pop(container_name, None)

        await proxy.stop()

        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def stop_all(self) -> None:
        """Stop all running proxies."""
        names = list(self._proxies.keys())
        for name in names:
            await self.stop_proxy(name)

    def list_proxies(self) -> list[tuple[str, str, int]]:
        """List all running proxies.

        Returns:
            List of (container_name, bus_address, name_count) tuples.
        """
        result = []
        for name, proxy in self._proxies.items():
            stats = proxy.get_stats()
            result.append((
                name,
                proxy._container_addr,
                stats["local_names"] + stats["host_names"],
            ))
        return result

    def get_proxy_stats(self, container_name: str) -> dict[str, int]:
        """Get statistics for a proxy.

        Args:
            container_name: Name of the container.

        Returns:
            Statistics dictionary.
        """
        if container_name not in self._proxies:
            return {}
        return self._proxies[container_name].get_stats()


class KapsuleService:
    """Main D-Bus service manager."""

    def __init__(
        self,
        bus_type: str = "session",
        host_bus_address: str | None = None,
    ):
        """Initialize the service.

        Args:
            bus_type: "session" or "system" bus for the daemon's own interface.
            host_bus_address: D-Bus address for host session bus (for proxying).
        """
        self._bus_type = BusType.SYSTEM if bus_type == "system" else BusType.SESSION
        self._bus: MessageBus | None = None
        self._proxy_manager = ProxyManager(host_bus_address)
        self._interface: KapsuleManagerInterface | None = None

    async def start(self) -> None:
        """Start the D-Bus service."""
        self._bus = await MessageBus(bus_type=self._bus_type).connect()

        self._interface = KapsuleManagerInterface(self._proxy_manager)

        # Export the interface at /org/kde/kapsule
        self._bus.export("/org/kde/kapsule", self._interface)

        # Request the well-known name
        await self._bus.request_name("org.kde.kapsule")

        bus_name = "system" if self._bus_type == BusType.SYSTEM else "session"
        print(f"Kapsule daemon v{__version__} running on {bus_name} bus")
        print("Service: org.kde.kapsule")
        print("Object:  /org/kde/kapsule")

    async def run(self) -> None:
        """Run the service until disconnected."""
        if self._bus is None:
            raise RuntimeError("Service not started")
        await self._bus.wait_for_disconnect()

    async def stop(self) -> None:
        """Stop the D-Bus service."""
        await self._proxy_manager.stop_all()
        if self._bus:
            self._bus.disconnect()
            self._bus = None

    @property
    def proxy_manager(self) -> ProxyManager:
        """Get the proxy manager."""
        return self._proxy_manager
