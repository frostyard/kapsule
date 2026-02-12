"""Nautilus extension for Kapsule container integration.

Adds "Open Terminal in Container" right-click submenu.
"""

from __future__ import annotations

import subprocess
import gi

gi.require_version("Nautilus", "4.0")
gi.require_version("Gio", "2.0")
from gi.repository import Nautilus, GObject, Gio, GLib

BUS_NAME = "org.frostyard.Kapsule"
OBJ_PATH = "/org/frostyard/Kapsule"
IFACE_NAME = "org.frostyard.Kapsule.Manager"


class KapsuleMenuProvider(GObject.GObject, Nautilus.MenuProvider):
    """Provides right-click menu items for Kapsule containers."""

    def __init__(self):
        super().__init__()
        self._containers: list[tuple[str, str]] = []
        self._refresh_containers()

    def _refresh_containers(self) -> None:
        """Fetch running containers from daemon via D-Bus."""
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            proxy = Gio.DBusProxy.new_sync(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                BUS_NAME,
                OBJ_PATH,
                IFACE_NAME,
                None,
            )
            result = proxy.call_sync(
                "ListContainers",
                None,
                Gio.DBusCallFlags.NONE,
                5000,
                None,
            )
            containers = result.unpack()[0]
            self._containers = [
                (name, status) for name, status, *_ in containers
            ]
        except Exception:
            self._containers = []

    def get_background_items(self, *args):
        """Add menu items when right-clicking directory background."""
        self._refresh_containers()

        running = [(n, s) for n, s in self._containers if s == "Running"]
        if not running:
            return []

        top_item = Nautilus.MenuItem(
            name="Kapsule::OpenTerminal",
            label="Open Terminal in Container",
        )

        submenu = Nautilus.Menu()
        top_item.set_submenu(submenu)

        for name, _ in running:
            item = Nautilus.MenuItem(
                name=f"Kapsule::Enter::{name}",
                label=name,
            )
            item.connect("activate", self._on_enter_container, name)
            submenu.append_item(item)

        return [top_item]

    def _on_enter_container(self, menu_item, container_name):
        """Open Ptyxis in the selected container."""
        subprocess.Popen(
            ["ptyxis", f"--tab-with-profile-name={container_name}"],
            start_new_session=True,
        )
