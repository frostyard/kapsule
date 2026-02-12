"""Create container dialog."""

from __future__ import annotations

import asyncio
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from kapsule.client import KapsuleClient


class CreateDialog(Adw.Dialog):
    """Dialog for creating a new container."""

    def __init__(self, on_created=None, **kwargs):
        super().__init__(**kwargs)

        self._on_created = on_created
        self.set_title("Create Container")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        # Name entry
        self._name_row = Adw.EntryRow(title="Name")
        box.append(self._name_row)

        # Image entry
        self._image_row = Adw.EntryRow(title="Image")
        self._image_row.set_text("images:archlinux")
        box.append(self._image_row)

        # Create button
        create_btn = Gtk.Button(label="Create")
        create_btn.add_css_class("suggested-action")
        create_btn.connect("clicked", self._on_create)
        box.append(create_btn)

        self.set_child(box)

    def _on_create(self, button):
        name = self._name_row.get_text().strip()
        image = self._image_row.get_text().strip()

        if not name:
            return

        button.set_sensitive(False)

        def create():
            loop = asyncio.new_event_loop()
            try:
                async def _create():
                    async with KapsuleClient() as client:
                        await client.create_container(name, image=image)
                loop.run_until_complete(_create())
                GLib.idle_add(self._on_success)
            except Exception:
                GLib.idle_add(button.set_sensitive, True)
            finally:
                loop.close()

        threading.Thread(target=create, daemon=True).start()

    def _on_success(self):
        if self._on_created:
            self._on_created()
        self.close()
