"""Container list row widget."""

from __future__ import annotations

import asyncio
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from kapsule.client import KapsuleClient


class ContainerRow(Adw.ActionRow):
    """A row representing a single container."""

    def __init__(self, container: dict, on_action=None):
        super().__init__()

        self._name = container["name"]
        self._status = container["status"]
        self._on_action = on_action

        self.set_title(self._name)
        self.set_subtitle(f"{container['image']} - {self._status}")

        # Action buttons
        if self._status == "Running":
            enter_btn = Gtk.Button(
                icon_name="utilities-terminal-symbolic",
                valign=Gtk.Align.CENTER,
                tooltip_text="Enter",
            )
            enter_btn.connect("clicked", self._on_enter)
            self.add_suffix(enter_btn)

            stop_btn = Gtk.Button(
                icon_name="media-playback-stop-symbolic",
                valign=Gtk.Align.CENTER,
                tooltip_text="Stop",
            )
            stop_btn.add_css_class("destructive-action")
            stop_btn.connect("clicked", self._on_stop)
            self.add_suffix(stop_btn)
        else:
            start_btn = Gtk.Button(
                icon_name="media-playback-start-symbolic",
                valign=Gtk.Align.CENTER,
                tooltip_text="Start",
            )
            start_btn.connect("clicked", self._on_start)
            self.add_suffix(start_btn)

        delete_btn = Gtk.Button(
            icon_name="user-trash-symbolic",
            valign=Gtk.Align.CENTER,
            tooltip_text="Delete",
        )
        delete_btn.add_css_class("destructive-action")
        delete_btn.connect("clicked", self._on_delete)
        self.add_suffix(delete_btn)

    def _run_async(self, coro, refresh_delay: float = 1.5):
        def run():
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(coro)
                if self._on_action:
                    GLib.timeout_add(
                        int(refresh_delay * 1000),
                        self._on_action,
                    )
            finally:
                loop.close()
        threading.Thread(target=run, daemon=True).start()

    def _on_enter(self, button):
        subprocess.Popen(
            ["ptyxis", f"--tab-with-profile-name={self._name}"],
            start_new_session=True,
        )

    def _on_start(self, button):
        async def _start():
            async with KapsuleClient() as client:
                await client.start_container(self._name)
        self._run_async(_start())

    def _on_stop(self, button):
        async def _stop():
            async with KapsuleClient() as client:
                await client.stop_container(self._name)
        self._run_async(_stop())

    def _on_delete(self, button):
        async def _delete():
            async with KapsuleClient() as client:
                await client.delete_container(self._name, force=True)
        self._run_async(_delete())
