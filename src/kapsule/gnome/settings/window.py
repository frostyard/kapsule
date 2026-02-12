"""Main application window."""

from __future__ import annotations

import asyncio
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from kapsule.client import KapsuleClient, DaemonNotRunning
from .container_row import ContainerRow
from .create_dialog import CreateDialog


class KapsuleWindow(Adw.ApplicationWindow):
    """Main window showing container list."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title("Kapsule")
        self.set_default_size(600, 400)

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        # Header bar
        header = Adw.HeaderBar()

        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.connect("clicked", self._on_create_clicked)
        header.pack_start(add_button)

        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_button.connect("clicked", lambda _: self._refresh())
        header.pack_end(refresh_button)

        # Content
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")

        self._status_page = Adw.StatusPage(
            icon_name="utilities-terminal-symbolic",
            title="No Containers",
            description="Create a container to get started.",
        )

        self._stack = Gtk.Stack()
        self._stack.add_named(self._status_page, "empty")

        scrolled = Gtk.ScrolledWindow(child=self._list_box)
        self._stack.add_named(scrolled, "list")

        clamp = Adw.Clamp(child=self._stack, maximum_size=600)

        # Toast overlay wraps the content area for in-app notifications
        self._toast_overlay = Adw.ToastOverlay(child=clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(header)
        box.append(self._toast_overlay)

        self.set_content(box)

    def _refresh(self):
        """Fetch containers from daemon in a background thread."""
        def fetch():
            loop = asyncio.new_event_loop()
            try:
                async def _get():
                    async with KapsuleClient() as client:
                        return await client.list_containers()
                containers = loop.run_until_complete(_get())
                GLib.idle_add(self._update_list, containers)
            except DaemonNotRunning:
                GLib.idle_add(self._show_daemon_error)
            except Exception as e:
                GLib.idle_add(self._show_toast, str(e))
            finally:
                loop.close()

        threading.Thread(target=fetch, daemon=True).start()

    def _update_list(self, containers):
        # Clear existing rows
        while row := self._list_box.get_first_child():
            self._list_box.remove(row)

        if not containers:
            self._stack.set_visible_child_name("empty")
            return

        self._stack.set_visible_child_name("list")
        for c in containers:
            row = ContainerRow(c, on_action=self._refresh)
            self._list_box.append(row)

    def _on_create_clicked(self, button):
        dialog = CreateDialog(on_created=self._refresh)
        dialog.present(self)

    def _show_daemon_error(self):
        self._show_toast(
            "Daemon not running. Start with: sudo systemctl start kapsule-daemon"
        )

    def _show_toast(self, message):
        toast = Adw.Toast(title=message, timeout=5)
        self._toast_overlay.add_toast(toast)
