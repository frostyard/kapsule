"""D-Bus service implementation for Kapsule.

Provides the org.kde.kapsule.Manager interface for container management.
"""

from __future__ import annotations

import asyncio

from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method, dbus_property, signal
from dbus_fast import BusType, Variant
from dbus_fast.constants import PropertyAccess

from . import __version__
from .container_service import ContainerService

# Re-export IncusClient for use in __main__ and CLI
from .incus_client import IncusClient


class KapsuleManagerInterface(ServiceInterface):
    """org.kde.kapsule.Manager D-Bus interface.

    This interface provides:
    - Container lifecycle management (create, delete, start, stop)
    - User setup in containers
    - Progress reporting via signals

    All long-running operations return an operation ID immediately.
    Progress is reported via signals that clients can subscribe to.
    """

    def __init__(self, container_service: ContainerService):
        super().__init__("org.kde.kapsule.Manager")
        self._service = container_service
        self._version = __version__

    # =========================================================================
    # Properties
    # =========================================================================

    @dbus_property(access=PropertyAccess.READ)
    def Version(self) -> "s":
        """Daemon version."""
        return self._version

    # =========================================================================
    # Signals for Operation Progress
    # =========================================================================

    @signal()
    def OperationStarted(
        self,
        operation_id: str,
        operation_type: str,
        description: str,
        target: str,
    ) -> "(ssss)":
        """Emitted when an operation begins.

        Args:
            operation_id: Unique ID for tracking this operation
            operation_type: Type of operation (create, delete, start, stop, setup_user)
            description: Human-readable description (e.g., "Creating container: mybox")
            target: Target of the operation (usually container name)
        """
        return (operation_id, operation_type, description, target)

    @signal()
    def OperationMessage(
        self,
        operation_id: str,
        message_type: int,
        message: str,
        indent_level: int,
    ) -> "(sisi)":
        """Emitted for progress messages within an operation.

        Args:
            operation_id: Operation this message belongs to
            message_type: Type of message (0=info, 1=success, 2=warning, 3=error, 4=dim, 5=hint)
            message: The message text
            indent_level: Indentation level for hierarchical display
        """
        return (operation_id, message_type, message, indent_level)

    @signal()
    def OperationCompleted(
        self,
        operation_id: str,
        success: bool,
        message: str,
    ) -> "(sbs)":
        """Emitted when an operation finishes.

        Args:
            operation_id: Operation that completed
            success: Whether the operation succeeded
            message: Final message (error message if failed)
        """
        return (operation_id, success, message)

    @signal()
    def ProgressStarted(
        self,
        operation_id: str,
        progress_id: str,
        description: str,
        total: int,
        indent_level: int,
    ) -> "(sssii)":
        """Emitted when a progress bar starts.

        Args:
            operation_id: Parent operation
            progress_id: Unique ID for this progress bar
            description: What's being tracked (e.g., "Downloading image...")
            total: Total units (-1 for indeterminate)
            indent_level: Indentation level
        """
        return (operation_id, progress_id, description, total, indent_level)

    @signal()
    def ProgressUpdate(
        self,
        progress_id: str,
        current: int,
        rate: float,
    ) -> "(sid)":
        """Emitted to update a progress bar.

        Args:
            progress_id: Progress bar to update
            current: Current progress value
            rate: Rate of progress (for ETA calculation)
        """
        return (progress_id, current, rate)

    @signal()
    def ProgressCompleted(
        self,
        progress_id: str,
        success: bool,
        message: str,
    ) -> "(sbs)":
        """Emitted when a progress bar completes.

        Args:
            progress_id: Progress bar that completed
            success: Whether it succeeded
            message: Optional completion message (replaces bar)
        """
        return (progress_id, success, message)

    # =========================================================================
    # Methods - Container Lifecycle
    # =========================================================================

    @method()
    async def CreateContainer(
        self,
        name: "s",
        image: "s",
        session_mode: "b",
        dbus_mux: "b",
    ) -> "s":
        """Create a new container.

        Args:
            name: Container name
            image: Image to use (e.g., "images:archlinux")
            session_mode: Enable session mode with container D-Bus
            dbus_mux: Enable D-Bus multiplexer (implies session_mode)

        Returns:
            Operation ID for tracking progress
        """
        return await self._service.create_container(
            name=name,
            image=image,
            session_mode=session_mode,
            dbus_mux=dbus_mux,
        )

    @method()
    async def DeleteContainer(self, name: "s", force: "b") -> "s":
        """Delete a container.

        Args:
            name: Container name
            force: Force removal even if running

        Returns:
            Operation ID for tracking progress
        """
        return await self._service.delete_container(name=name, force=force)

    @method()
    async def StartContainer(self, name: "s") -> "s":
        """Start a stopped container.

        Args:
            name: Container name

        Returns:
            Operation ID for tracking progress
        """
        return await self._service.start_container(name=name)

    @method()
    async def StopContainer(self, name: "s", force: "b") -> "s":
        """Stop a running container.

        Args:
            name: Container name
            force: Force stop

        Returns:
            Operation ID for tracking progress
        """
        return await self._service.stop_container(name=name, force=force)

    # =========================================================================
    # Methods - User Setup
    # =========================================================================

    @method()
    async def SetupUser(
        self,
        container_name: "s",
        uid: "u",
        gid: "u",
        username: "s",
        home_dir: "s",
    ) -> "s":
        """Set up a host user in a container.

        This mounts the user's home directory and creates a matching
        user account with passwordless sudo.

        Args:
            container_name: Container name
            uid: User ID
            gid: Group ID
            username: Username
            home_dir: Path to home directory on host

        Returns:
            Operation ID for tracking progress
        """
        return await self._service.setup_user(
            container_name=container_name,
            uid=uid,
            gid=gid,
            username=username,
            home_dir=home_dir,
        )

    @method()
    async def IsUserSetup(self, container_name: "s", uid: "u") -> "b":
        """Check if a user is set up in a container.

        Args:
            container_name: Container name
            uid: User ID to check

        Returns:
            True if user is set up
        """
        return await self._service.is_user_setup(container_name, uid)

    # =========================================================================
    # Methods - Query
    # =========================================================================

    @method()
    async def ListContainers(self) -> "a(sssss)":
        """List all containers.

        Returns:
            Array of (name, status, image, created, mode) tuples
        """
        return await self._service.list_containers()

    @method()
    async def GetContainerInfo(self, name: "s") -> "a{ss}":
        """Get detailed information about a container.

        Args:
            name: Container name

        Returns:
            Dictionary with container details
        """
        return await self._service.get_container_info(name)


class KapsuleService:
    """Main D-Bus service manager.

    Handles D-Bus connection lifecycle and hosts the KapsuleManagerInterface.
    """

    def __init__(
        self,
        bus_type: str = "system",
        socket_path: str = "/var/lib/incus/unix.socket",
    ):
        """Initialize the service.

        Args:
            bus_type: "session" or "system" bus for the daemon's interface
            socket_path: Path to Incus Unix socket
        """
        self._bus_type = BusType.SYSTEM if bus_type == "system" else BusType.SESSION
        self._socket_path = socket_path
        self._bus: MessageBus | None = None
        self._interface: KapsuleManagerInterface | None = None
        self._incus: IncusClient | None = None
        self._container_service: ContainerService | None = None

    async def start(self) -> None:
        """Start the D-Bus service."""
        # Connect to D-Bus
        self._bus = await MessageBus(bus_type=self._bus_type).connect()

        # Create Incus client
        self._incus = IncusClient(socket_path=self._socket_path)

        # Create the interface and container service
        # The interface needs the service, and the service needs the interface
        # So we create them in two steps using __new__
        temp_interface = KapsuleManagerInterface.__new__(KapsuleManagerInterface)
        ServiceInterface.__init__(temp_interface, "org.kde.kapsule.Manager")
        temp_interface._version = __version__

        self._container_service = ContainerService(temp_interface, self._incus)
        temp_interface._service = self._container_service

        self._interface = temp_interface

        # Export the interface
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
        if self._incus:
            await self._incus.close()
            self._incus = None

        if self._bus:
            self._bus.disconnect()
            self._bus = None

    @property
    def container_service(self) -> ContainerService | None:
        """Get the container service."""
        return self._container_service
