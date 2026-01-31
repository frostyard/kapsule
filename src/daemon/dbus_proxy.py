"""D-Bus proxy for container session bus with host fallback.

This module provides a proxy that gives containers their own D-Bus session bus
while transparently forwarding calls to the host for services not registered locally.

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                     Container                                │
    │  ┌─────────────────────────────────────────────────────┐   │
    │  │              Container Session Bus                    │   │
    │  │         (dbus-daemon in container)                   │   │
    │  └────────────────────────┬────────────────────────────┘   │
    │                           │                                  │
    │  ┌────────────────────────▼────────────────────────────┐   │
    │  │           DBusProxy                                  │   │
    │  │  • Monitors NameOwnerChanged on both buses          │   │
    │  │  • Maintains routing table (local vs host)          │   │
    │  │  • Forwards unhandled calls to host                 │   │
    │  │  • Rewrites message serial numbers                  │   │
    │  └────────────────────────┬────────────────────────────┘   │
    │                           │                                  │
    └───────────────────────────┼──────────────────────────────────┘
                                │ (unix socket passthrough)
    ┌───────────────────────────▼──────────────────────────────────┐
    │                     Host Session Bus                          │
    │              $XDG_RUNTIME_DIR/bus                             │
    └───────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from dbus_fast import BusType, Message, MessageType
from dbus_fast.aio import MessageBus


class NameLocation(Enum):
    """Where a D-Bus name is registered."""

    LOCAL = "local"  # Container's own bus
    HOST = "host"  # Host session bus


@dataclass
class PendingCall:
    """Tracks a forwarded method call awaiting reply."""

    original_serial: int
    source: Literal["local", "host"]
    reply_future: asyncio.Future[Message]


@dataclass
class ProxyState:
    """Mutable state for the D-Bus proxy."""

    # Name routing table: well-known name -> location
    name_routes: dict[str, NameLocation] = field(default_factory=dict)

    # Activatable names (services that can be started on demand)
    host_activatable: set[str] = field(default_factory=set)
    local_activatable: set[str] = field(default_factory=set)

    # Pending method calls: (bus, serial) -> PendingCall
    pending_calls: dict[tuple[str, int], PendingCall] = field(default_factory=dict)

    # Serial number counter for forwarded messages
    next_serial: int = 1


class DBusProxy:
    """Proxy between container D-Bus session and host session bus.

    Enables containers to have their own session bus while falling back
    to host services for names not registered locally.
    """

    # D-Bus daemon well-known name
    DBUS_NAME = "org.freedesktop.DBus"
    DBUS_PATH = "/org/freedesktop/DBus"
    DBUS_INTERFACE = "org.freedesktop.DBus"

    def __init__(
        self,
        container_bus_address: str,
        host_bus_address: str | None = None,
    ):
        """Initialize the proxy.

        Args:
            container_bus_address: D-Bus address for the container's session bus.
                Example: "unix:path=/run/user/1000/kapsule/mycontainer/bus"
            host_bus_address: D-Bus address for host session bus.
                If None, uses DBUS_SESSION_BUS_ADDRESS or default session bus.
        """
        self._container_addr = container_bus_address
        self._host_addr = host_bus_address or os.environ.get("DBUS_SESSION_BUS_ADDRESS")

        self._container_bus: MessageBus | None = None
        self._host_bus: MessageBus | None = None

        self._state = ProxyState()
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Connect to both buses and initialize name tracking."""
        # Connect to host bus first (it must exist)
        if self._host_addr:
            self._host_bus = MessageBus(bus_address=self._host_addr)
        else:
            self._host_bus = MessageBus(bus_type=BusType.SESSION)
        self._host_bus._negotiate_unix_fd = True
        await self._host_bus.connect()

        # Connect to container bus
        self._container_bus = MessageBus(bus_address=self._container_addr)
        self._container_bus._negotiate_unix_fd = True
        await self._container_bus.connect()

        # Type narrowing assertion - buses are connected at this point
        assert self._host_bus is not None
        assert self._container_bus is not None

        # Initialize name routing tables
        await self._init_name_routing()

        # Subscribe to NameOwnerChanged on both buses
        await self._subscribe_name_changes()

        # Set up message handlers
        self._host_bus.add_message_handler(self._on_host_message)
        self._container_bus.add_message_handler(self._on_container_message)

        self._running = True
        print(f"D-Bus proxy started")
        print(f"  Container bus: {self._container_addr}")
        print(f"  Host bus: {self._host_addr or 'session'}")
        print(f"  Tracked names: {len(self._state.name_routes)} local, "
              f"{len(self._state.host_activatable)} host activatable")

    async def _init_name_routing(self) -> None:
        """Initialize the name routing table from both buses."""
        # Get names from host bus
        host_names = await self._list_names(self._host_bus)
        host_activatable = await self._list_activatable_names(self._host_bus)

        # Get names from container bus
        local_names = await self._list_names(self._container_bus)
        local_activatable = await self._list_activatable_names(self._container_bus)

        # Build routing table
        # Local names take priority (container can shadow host services)
        for name in host_names:
            if not name.startswith(":"):  # Skip unique names
                self._state.name_routes[name] = NameLocation.HOST

        for name in local_names:
            if not name.startswith(":"):
                self._state.name_routes[name] = NameLocation.LOCAL

        self._state.host_activatable = set(host_activatable)
        self._state.local_activatable = set(local_activatable)

    async def _list_names(self, bus: MessageBus) -> list[str]:
        """Call org.freedesktop.DBus.ListNames()."""
        reply = await bus.call(
            Message(
                destination=self.DBUS_NAME,
                path=self.DBUS_PATH,
                interface=self.DBUS_INTERFACE,
                member="ListNames",
            )
        )
        if reply.message_type == MessageType.METHOD_RETURN and reply.body:
            return reply.body[0]
        return []

    async def _list_activatable_names(self, bus: MessageBus) -> list[str]:
        """Call org.freedesktop.DBus.ListActivatableNames()."""
        reply = await bus.call(
            Message(
                destination=self.DBUS_NAME,
                path=self.DBUS_PATH,
                interface=self.DBUS_INTERFACE,
                member="ListActivatableNames",
            )
        )
        if reply.message_type == MessageType.METHOD_RETURN and reply.body:
            return reply.body[0]
        return []

    async def _subscribe_name_changes(self) -> None:
        """Subscribe to NameOwnerChanged signals on both buses."""
        match_rule = (
            "type='signal',"
            "sender='org.freedesktop.DBus',"
            "interface='org.freedesktop.DBus',"
            "member='NameOwnerChanged'"
        )

        # Add match rules
        for bus in (self._host_bus, self._container_bus):
            await bus.call(
                Message(
                    destination=self.DBUS_NAME,
                    path=self.DBUS_PATH,
                    interface=self.DBUS_INTERFACE,
                    member="AddMatch",
                    signature="s",
                    body=[match_rule],
                )
            )

    def _on_host_message(self, msg: Message) -> bool:
        """Handle messages from the host bus.

        Returns:
            True if message was handled (stops further processing).
        """
        # Handle NameOwnerChanged signals
        if (
            msg.message_type == MessageType.SIGNAL
            and msg.member == "NameOwnerChanged"
            and msg.interface == self.DBUS_INTERFACE
        ):
            self._handle_host_name_change(msg)
            return False  # Let other handlers see it too

        # Handle replies to forwarded calls
        if msg.message_type in (MessageType.METHOD_RETURN, MessageType.ERROR):
            key = ("host", msg.reply_serial)
            if key in self._state.pending_calls:
                pending = self._state.pending_calls.pop(key)
                if not pending.reply_future.done():
                    pending.reply_future.set_result(msg)
                return True

        return False

    def _on_container_message(self, msg: Message) -> bool:
        """Handle messages from the container bus.

        Returns:
            True if message was handled.
        """
        # Handle NameOwnerChanged signals
        if (
            msg.message_type == MessageType.SIGNAL
            and msg.member == "NameOwnerChanged"
            and msg.interface == self.DBUS_INTERFACE
        ):
            self._handle_local_name_change(msg)
            return False

        # Handle replies to forwarded calls
        if msg.message_type in (MessageType.METHOD_RETURN, MessageType.ERROR):
            key = ("local", msg.reply_serial)
            if key in self._state.pending_calls:
                pending = self._state.pending_calls.pop(key)
                if not pending.reply_future.done():
                    pending.reply_future.set_result(msg)
                return True

        return False

    def _handle_host_name_change(self, msg: Message) -> None:
        """Handle NameOwnerChanged from host bus."""
        if not msg.body or len(msg.body) < 3:
            return

        name, old_owner, new_owner = msg.body[0], msg.body[1], msg.body[2]

        if name.startswith(":"):
            return  # Ignore unique connection names

        if new_owner:
            # Name acquired on host - only add if not locally owned
            if self._state.name_routes.get(name) != NameLocation.LOCAL:
                self._state.name_routes[name] = NameLocation.HOST
        else:
            # Name released on host
            if self._state.name_routes.get(name) == NameLocation.HOST:
                del self._state.name_routes[name]

    def _handle_local_name_change(self, msg: Message) -> None:
        """Handle NameOwnerChanged from container bus."""
        if not msg.body or len(msg.body) < 3:
            return

        name, old_owner, new_owner = msg.body[0], msg.body[1], msg.body[2]

        if name.startswith(":"):
            return

        if new_owner:
            # Name acquired locally - takes priority over host
            self._state.name_routes[name] = NameLocation.LOCAL
        else:
            # Name released locally - fall back to host if available
            if name in self._state.name_routes:
                del self._state.name_routes[name]
            # Check if host has this name
            asyncio.create_task(self._check_host_has_name(name))

    async def _check_host_has_name(self, name: str) -> None:
        """Check if host bus has a name and update routing."""
        if not self._host_bus:
            return
        try:
            reply = await self._host_bus.call(
                Message(
                    destination=self.DBUS_NAME,
                    path=self.DBUS_PATH,
                    interface=self.DBUS_INTERFACE,
                    member="GetNameOwner",
                    signature="s",
                    body=[name],
                )
            )
            if reply.message_type == MessageType.METHOD_RETURN:
                self._state.name_routes[name] = NameLocation.HOST
        except Exception:
            pass  # Name doesn't exist on host either

    def _get_route(self, destination: str | None) -> NameLocation | None:
        """Determine where to route a message based on destination.

        Args:
            destination: The D-Bus destination name.

        Returns:
            NameLocation.LOCAL, NameLocation.HOST, or None if unknown.
        """
        if not destination:
            return None

        # Unique names (starting with :) stay on their originating bus
        if destination.startswith(":"):
            return None

        # Check routing table
        if destination in self._state.name_routes:
            return self._state.name_routes[destination]

        # Check if activatable on host
        if destination in self._state.host_activatable:
            return NameLocation.HOST

        # Check if activatable locally
        if destination in self._state.local_activatable:
            return NameLocation.LOCAL

        # Default to host for unknown names (allows host service activation)
        return NameLocation.HOST

    async def forward_to_host(self, msg: Message) -> Message | None:
        """Forward a message from container to host bus.

        Args:
            msg: The message to forward.

        Returns:
            The reply message, or None if no reply expected.
        """
        if not self._host_bus:
            return None

        # Create forwarded message with new serial
        serial = self._state.next_serial
        self._state.next_serial += 1

        forwarded = Message(
            destination=msg.destination,
            path=msg.path,
            interface=msg.interface,
            member=msg.member,
            signature=msg.signature,
            body=msg.body,
            unix_fds=msg.unix_fds,  # Forward file descriptors
        )

        if msg.flags & 0x01:  # NO_REPLY_EXPECTED
            self._host_bus.send(forwarded)
            return None

        # Track pending call for reply correlation
        future: asyncio.Future[Message] = asyncio.get_event_loop().create_future()
        self._state.pending_calls[("host", serial)] = PendingCall(
            original_serial=msg.serial,
            source="local",
            reply_future=future,
        )

        self._host_bus.send(forwarded)

        try:
            reply = await asyncio.wait_for(future, timeout=30.0)
            # Return reply with unix_fds preserved
            return reply
        except asyncio.TimeoutError:
            self._state.pending_calls.pop(("host", serial), None)
            return None

    async def forward_to_local(self, msg: Message) -> Message | None:
        """Forward a message from host to container bus.

        Args:
            msg: The message to forward.

        Returns:
            The reply message, or None if no reply expected.
        """
        if not self._container_bus:
            return None

        serial = self._state.next_serial
        self._state.next_serial += 1

        forwarded = Message(
            destination=msg.destination,
            path=msg.path,
            interface=msg.interface,
            member=msg.member,
            signature=msg.signature,
            body=msg.body,
            unix_fds=msg.unix_fds,
        )

        if msg.flags & 0x01:
            self._container_bus.send(forwarded)
            return None

        future: asyncio.Future[Message] = asyncio.get_event_loop().create_future()
        self._state.pending_calls[("local", serial)] = PendingCall(
            original_serial=msg.serial,
            source="host",
            reply_future=future,
        )

        self._container_bus.send(forwarded)

        try:
            reply = await asyncio.wait_for(future, timeout=30.0)
            return reply
        except asyncio.TimeoutError:
            self._state.pending_calls.pop(("local", serial), None)
            return None

    async def run(self) -> None:
        """Run the proxy until shutdown."""
        if not self._running:
            raise RuntimeError("Proxy not started")

        await self._shutdown_event.wait()

    async def stop(self) -> None:
        """Stop the proxy and close connections."""
        self._running = False
        self._shutdown_event.set()

        # Cancel pending calls
        for pending in self._state.pending_calls.values():
            if not pending.reply_future.done():
                pending.reply_future.cancel()
        self._state.pending_calls.clear()

        # Disconnect buses
        if self._container_bus:
            self._container_bus.disconnect()
            self._container_bus = None

        if self._host_bus:
            self._host_bus.disconnect()
            self._host_bus = None

    @property
    def is_running(self) -> bool:
        """Whether the proxy is currently running."""
        return self._running

    def get_stats(self) -> dict:
        """Get proxy statistics."""
        return {
            "local_names": sum(
                1 for loc in self._state.name_routes.values()
                if loc == NameLocation.LOCAL
            ),
            "host_names": sum(
                1 for loc in self._state.name_routes.values()
                if loc == NameLocation.HOST
            ),
            "host_activatable": len(self._state.host_activatable),
            "local_activatable": len(self._state.local_activatable),
            "pending_calls": len(self._state.pending_calls),
        }
