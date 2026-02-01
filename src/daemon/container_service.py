"""Container lifecycle operations for the Kapsule daemon.

This module implements the core container management operations,
using the operation decorator for automatic progress reporting.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

from .operations import OperationError, OperationReporter, OperationTracker, operation

if TYPE_CHECKING:
    from .service import KapsuleManagerInterface

# Import Incus client and models from local modules
from .incus_client import IncusClient, IncusError
from .models_generated import InstanceSource, InstancesPost
from .profile import KAPSULE_BASE_PROFILE, KAPSULE_PROFILE_NAME


# Config keys for kapsule metadata stored in container config
KAPSULE_SESSION_MODE_KEY = "user.kapsule.session-mode"
KAPSULE_DBUS_MUX_KEY = "user.kapsule.dbus-mux"

# Path to kapsule-dbus-mux binary inside container (via hostfs mount)
KAPSULE_DBUS_MUX_BIN = "/.kapsule/host/usr/lib/kapsule/kapsule-dbus-mux"

# D-Bus socket path template using %t (systemd specifier for XDG_RUNTIME_DIR)
KAPSULE_DBUS_SOCKET_USER_PATH = "kapsule/{container}/dbus.socket"
KAPSULE_DBUS_SOCKET_SYSTEMD = "/.kapsule/host%t/" + KAPSULE_DBUS_SOCKET_USER_PATH


class ContainerService:
    """Container lifecycle operations exposed over D-Bus.

    Each public method decorated with @operation becomes a D-Bus method
    that returns an operation ID. Progress is reported via D-Bus signals.
    """

    def __init__(
        self,
        interface: "KapsuleManagerInterface",
        incus: IncusClient,
    ):
        """Initialize the container service.

        Args:
            interface: D-Bus interface for emitting signals
            incus: Incus API client
        """
        self._interface = interface
        self._incus = incus
        self._tracker = OperationTracker()

    # -------------------------------------------------------------------------
    # Container Lifecycle Operations
    # -------------------------------------------------------------------------

    @operation(
        "create",
        description=lambda name, **_: f"Creating container: {name}",
        target_param="name",
    )
    async def create_container(
        self,
        progress: OperationReporter,
        *,
        name: str,
        image: str,
        session_mode: bool = False,
        dbus_mux: bool = False,
    ) -> None:
        """Create a new container.

        Args:
            progress: Operation reporter (auto-injected)
            name: Container name
            image: Image to use (e.g., "images:archlinux")
            session_mode: Enable session mode with container D-Bus
            dbus_mux: Enable D-Bus multiplexer (implies session_mode)
        """
        # dbus_mux implies session_mode
        if dbus_mux:
            session_mode = True

        # Check if container already exists
        if await self._incus.instance_exists(name):
            raise OperationError(f"Container '{name}' already exists")

        # Ensure profile exists
        await self._ensure_profile(progress)

        progress.info(f"Image: {image}")

        # Parse image source
        instance_source = self._parse_image_source(image)
        if instance_source is None:
            raise OperationError(f"Invalid image format: {image}")

        # Build instance config
        instance_metadata: dict[str, str] = {}
        if session_mode:
            instance_metadata[KAPSULE_SESSION_MODE_KEY] = "true"
        if dbus_mux:
            instance_metadata[KAPSULE_DBUS_MUX_KEY] = "true"

        instance_config = InstancesPost(
            name=name,
            profiles=[KAPSULE_PROFILE_NAME],
            source=instance_source,
            start=True,
            architecture=None,
            config=instance_metadata if instance_metadata else None,
            description=None,
            devices=None,
            ephemeral=None,
            instance_type=None,
            restore=None,
            stateful=None,
            type=None,
        )

        # Create the container
        progress.info("Downloading image and creating container...")
        try:
            operation = await self._incus.create_instance(instance_config, wait=True)
            if operation.status != "Success":
                raise OperationError(f"Creation failed: {operation.err or operation.status}")
        except IncusError as e:
            raise OperationError(f"Failed to create container: {e}")

        # Set up session mode if enabled
        if session_mode:
            await self._setup_session_mode(progress, name, dbus_mux)

        progress.success(f"Container '{name}' created successfully")

    @operation(
        "delete",
        description=lambda name, **_: f"Removing container: {name}",
        target_param="name",
    )
    async def delete_container(
        self,
        progress: OperationReporter,
        *,
        name: str,
        force: bool = False,
    ) -> None:
        """Delete a container.

        Args:
            progress: Operation reporter (auto-injected)
            name: Container name
            force: Force removal even if running
        """
        # Check existence
        if not await self._incus.instance_exists(name):
            raise OperationError(f"Container '{name}' does not exist")

        instance = await self._incus.get_instance(name)
        is_running = instance.status and instance.status.lower() == "running"

        if is_running and not force:
            raise OperationError(f"Container '{name}' is running. Use force=True to remove anyway.")

        if is_running:
            progress.info("Stopping container...")
            try:
                op = await self._incus.stop_instance(name, force=True, wait=True)
                if op.status != "Success":
                    raise OperationError(f"Failed to stop: {op.err or op.status}")
            except IncusError as e:
                raise OperationError(f"Failed to stop container: {e}")
            progress.success("Container stopped")

        progress.info("Deleting container...")
        try:
            op = await self._incus.delete_instance(name, wait=True)
            if op.status != "Success":
                raise OperationError(f"Deletion failed: {op.err or op.status}")
        except IncusError as e:
            raise OperationError(f"Failed to delete container: {e}")

        progress.success(f"Container '{name}' removed successfully")

    @operation(
        "start",
        description=lambda name, **_: f"Starting container: {name}",
        target_param="name",
    )
    async def start_container(
        self,
        progress: OperationReporter,
        *,
        name: str,
    ) -> None:
        """Start a stopped container.

        Args:
            progress: Operation reporter (auto-injected)
            name: Container name
        """
        if not await self._incus.instance_exists(name):
            raise OperationError(f"Container '{name}' does not exist")

        instance = await self._incus.get_instance(name)
        if instance.status and instance.status.lower() == "running":
            progress.warning(f"Container '{name}' is already running")
            return

        progress.info("Starting container...")
        try:
            op = await self._incus.start_instance(name, wait=True)
            if op.status != "Success":
                raise OperationError(f"Start failed: {op.err or op.status}")
        except IncusError as e:
            raise OperationError(f"Failed to start container: {e}")

        progress.success(f"Container '{name}' started successfully")

    @operation(
        "stop",
        description=lambda name, **_: f"Stopping container: {name}",
        target_param="name",
    )
    async def stop_container(
        self,
        progress: OperationReporter,
        *,
        name: str,
        force: bool = False,
    ) -> None:
        """Stop a running container.

        Args:
            progress: Operation reporter (auto-injected)
            name: Container name
            force: Force stop
        """
        if not await self._incus.instance_exists(name):
            raise OperationError(f"Container '{name}' does not exist")

        instance = await self._incus.get_instance(name)
        if instance.status and instance.status.lower() != "running":
            progress.warning(f"Container '{name}' is not running")
            return

        progress.info("Stopping container...")
        try:
            op = await self._incus.stop_instance(name, force=force, wait=True)
            if op.status != "Success":
                raise OperationError(f"Stop failed: {op.err or op.status}")
        except IncusError as e:
            raise OperationError(f"Failed to stop container: {e}")

        progress.success(f"Container '{name}' stopped successfully")

    # -------------------------------------------------------------------------
    # User Setup Operations
    # -------------------------------------------------------------------------

    @operation(
        "setup_user",
        description=lambda container_name, username, **_: f"Setting up user '{username}' in {container_name}",
        target_param="container_name",
    )
    async def setup_user(
        self,
        progress: OperationReporter,
        *,
        container_name: str,
        uid: int,
        gid: int,
        username: str,
        home_dir: str,
    ) -> None:
        """Set up a host user in a container.

        This mounts the user's home directory and creates a matching
        user account in the container with passwordless sudo.

        Args:
            progress: Operation reporter (auto-injected)
            container_name: Container name
            uid: User ID
            gid: Group ID
            username: Username
            home_dir: Path to home directory on host
        """
        home_basename = os.path.basename(home_dir)
        container_home = f"/home/{home_basename}"

        # Mount home directory
        progress.info(f"Mounting home directory: {home_dir} -> {container_home}")
        device_name = f"kapsule-home-{username}"
        try:
            await self._incus.add_instance_device(
                container_name,
                device_name,
                {
                    "type": "disk",
                    "source": home_dir,
                    "path": container_home,
                },
            )
        except IncusError as e:
            raise OperationError(f"Failed to mount home directory: {e}")

        # Create group
        progress.info(f"Creating group '{username}' (gid={gid})")
        result = subprocess.run(
            ["incus", "exec", container_name, "--", "groupadd", "-o", "-g", str(gid), username],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and "already exists" not in result.stderr:
            progress.warning(f"groupadd: {result.stderr.strip()}")

        # Create user
        progress.info(f"Creating user '{username}' (uid={uid})")
        result = subprocess.run(
            [
                "incus",
                "exec",
                container_name,
                "--",
                "useradd",
                "-o",  # Allow duplicate UID
                "-M",  # Don't create home directory
                "-u",
                str(uid),
                "-g",
                str(gid),
                "-d",
                container_home,
                "-s",
                "/bin/bash",
                username,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and "already exists" not in result.stderr:
            progress.warning(f"useradd: {result.stderr.strip()}")

        # Configure passwordless sudo
        progress.info(f"Configuring passwordless sudo for '{username}'")
        sudoers_content = f"{username} ALL=(ALL) NOPASSWD:ALL\n"
        sudoers_file = f"/etc/sudoers.d/{username}"
        try:
            await self._incus.push_file(
                container_name,
                sudoers_file,
                sudoers_content,
                uid=0,
                gid=0,
                mode="0440",
            )
        except IncusError as e:
            raise OperationError(f"Failed to configure sudo: {e}")

        # Check if session mode is enabled
        instance = await self._incus.get_instance(container_name)
        instance_config = instance.config or {}
        session_mode = instance_config.get(KAPSULE_SESSION_MODE_KEY) == "true"

        if session_mode:
            progress.info(f"Enabling linger for '{username}' (session mode)")
            result = subprocess.run(
                ["incus", "exec", container_name, "--", "loginctl", "enable-linger", username],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                progress.warning(f"loginctl enable-linger: {result.stderr.strip()}")

        # Mark user as mapped
        user_mapped_key = f"user.kapsule.host-users.{uid}.mapped"
        try:
            await self._incus.patch_instance_config(container_name, {user_mapped_key: "true"})
        except IncusError as e:
            raise OperationError(f"Failed to update container config: {e}")

        progress.success(f"User '{username}' configured")

    # -------------------------------------------------------------------------
    # Query Methods (non-operation, synchronous response)
    # -------------------------------------------------------------------------

    async def list_containers(self) -> list[tuple[str, str, str, str, str]]:
        """List all containers.

        Returns:
            List of (name, status, image, created, kapsule_mode) tuples
        """
        containers = await self._incus.list_containers()
        result = []
        for c in containers:
            # Get kapsule mode from instance config
            try:
                instance = await self._incus.get_instance(c.name)
                config = instance.config or {}
                if config.get(KAPSULE_DBUS_MUX_KEY) == "true":
                    mode = "dbus-mux"
                elif config.get(KAPSULE_SESSION_MODE_KEY) == "true":
                    mode = "session"
                else:
                    mode = "default"
            except IncusError:
                mode = "unknown"

            result.append((c.name, c.status, c.image, c.created, mode))
        return result

    async def get_container_info(self, name: str) -> dict[str, str]:
        """Get detailed container information.

        Args:
            name: Container name

        Returns:
            Dictionary with container details
        """
        try:
            instance = await self._incus.get_instance(name)
        except IncusError as e:
            raise OperationError(f"Container '{name}' not found: {e}")

        config = instance.config or {}
        return {
            "name": instance.name or name,
            "status": instance.status or "Unknown",
            "session_mode": config.get(KAPSULE_SESSION_MODE_KEY, "false"),
            "dbus_mux": config.get(KAPSULE_DBUS_MUX_KEY, "false"),
            "image": config.get("image.description", config.get("image.os", "unknown")),
        }

    async def is_user_setup(self, container_name: str, uid: int) -> bool:
        """Check if a user is already set up in a container.

        Args:
            container_name: Container name
            uid: User ID to check

        Returns:
            True if user is set up
        """
        try:
            instance = await self._incus.get_instance(container_name)
            config = instance.config or {}
            return config.get(f"user.kapsule.host-users.{uid}.mapped") == "true"
        except IncusError:
            return False

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    async def _ensure_profile(self, progress: OperationReporter) -> None:
        """Ensure the kapsule profile exists."""
        progress.info(f"Ensuring profile: {KAPSULE_PROFILE_NAME}")
        sub = progress.indented()

        try:
            created = await self._incus.ensure_profile(KAPSULE_PROFILE_NAME, KAPSULE_BASE_PROFILE)
            if created:
                sub.success(f"Created profile '{KAPSULE_PROFILE_NAME}'")
            else:
                sub.dim(f"Profile '{KAPSULE_PROFILE_NAME}' already exists")
        except IncusError as e:
            raise OperationError(f"Failed to ensure profile: {e}")

    def _parse_image_source(self, image: str) -> InstanceSource | None:
        """Parse an image string into an InstanceSource.

        Args:
            image: Image string like "images:archlinux" or "ubuntu:24.04"

        Returns:
            InstanceSource or None if invalid
        """
        # Map common server aliases to URLs
        server_map = {
            "images": "https://images.linuxcontainers.org",
            "ubuntu": "https://cloud-images.ubuntu.com/releases",
        }

        if ":" in image:
            server_alias, image_alias = image.split(":", 1)
            server_url = server_map.get(server_alias)
            if not server_url:
                return None
        else:
            server_url = "https://images.linuxcontainers.org"
            image_alias = image

        return InstanceSource(
            type="image",
            protocol="simplestreams",
            server=server_url,
            alias=image_alias,
            allow_inconsistent=None,
            certificate=None,
            fingerprint=None,
            instance_only=None,
            live=None,
            mode=None,
            operation=None,
            project=None,
            properties=None,
            refresh=None,
            refresh_exclude_older=None,
            secret=None,
            secrets=None,
            source=None,
            **{"base-image": None},
        )

    async def _setup_session_mode(
        self,
        progress: OperationReporter,
        name: str,
        dbus_mux: bool,
    ) -> None:
        """Set up session mode for a container.

        Args:
            progress: Operation reporter
            name: Container name
            dbus_mux: Whether to set up D-Bus multiplexer
        """
        # Use uid 1000 as placeholder - the drop-in uses %t so it works for any user
        uid = 1000
        host_socket_path = f"/run/user/{uid}/kapsule/{name}/dbus.socket"

        progress.info(f"Configuring container D-Bus socket at: {host_socket_path}")

        # Create the directory on host
        host_socket_dir = os.path.dirname(host_socket_path)
        os.makedirs(host_socket_dir, exist_ok=True)

        # Create systemd user drop-in directory
        dropin_dir = "/etc/systemd/user/dbus.socket.d"
        try:
            await self._incus.mkdir(name, dropin_dir, uid=0, gid=0, mode="0755")
        except IncusError:
            pass  # Directory might already exist

        # Create the drop-in file
        systemd_socket_path = KAPSULE_DBUS_SOCKET_SYSTEMD.format(container=name)
        dropin_content = f"""[Socket]
# Kapsule: redirect D-Bus session socket to shared path
# This makes the container's D-Bus accessible from the host
# %t expands to XDG_RUNTIME_DIR (/run/user/UID)
ListenStream=
ListenStream={systemd_socket_path}
"""
        dropin_file = f"{dropin_dir}/kapsule.conf"
        try:
            await self._incus.push_file(name, dropin_file, dropin_content, uid=0, gid=0, mode="0644")
        except IncusError as e:
            raise OperationError(f"Failed to configure D-Bus socket: {e}")

        # Set up D-Bus multiplexer if requested
        if dbus_mux:
            await self._setup_dbus_mux(progress, name)

        # Reload systemd
        progress.info("Reloading systemd user configuration...")
        subprocess.run(
            ["incus", "exec", name, "--", "systemctl", "--user", "--global", "daemon-reload"],
            capture_output=True,
        )

    async def _setup_dbus_mux(self, progress: OperationReporter, name: str) -> None:
        """Set up D-Bus multiplexer service in a container.

        Args:
            progress: Operation reporter
            name: Container name
        """
        progress.info("Installing kapsule-dbus-mux.service for D-Bus multiplexing")

        service_dir = "/etc/systemd/user"
        try:
            await self._incus.mkdir(name, service_dir, uid=0, gid=0, mode="0755")
        except IncusError:
            pass  # Directory might already exist

        container_dbus_socket = KAPSULE_DBUS_SOCKET_SYSTEMD.format(container=name)
        host_dbus_socket = "unix:path=/.kapsule/host%t/bus"
        mux_listen_socket = "%t/bus"

        service_content = f"""[Unit]
Description=Kapsule D-Bus Multiplexer
Documentation=man:kapsule(1)
After=dbus.service
Requires=dbus.service

[Service]
Type=simple
ExecStart={KAPSULE_DBUS_MUX_BIN} \\
    --listen {mux_listen_socket} \\
    --container-bus unix:path={container_dbus_socket} \\
    --host-bus {host_dbus_socket}
Restart=on-failure
RestartSec=1

[Install]
WantedBy=default.target
"""

        service_file = f"{service_dir}/kapsule-dbus-mux.service"
        try:
            await self._incus.push_file(name, service_file, service_content, uid=0, gid=0, mode="0644")
        except IncusError as e:
            raise OperationError(f"Failed to install dbus-mux service: {e}")

        progress.info("Enabling kapsule-dbus-mux.service globally")
        subprocess.run(
            ["incus", "exec", name, "--", "systemctl", "--user", "--global", "enable", "kapsule-dbus-mux.service"],
            capture_output=True,
        )
