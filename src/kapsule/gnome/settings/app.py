"""Kapsule Settings GTK4/libadwaita application."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio

from .window import KapsuleWindow


class KapsuleApp(Adw.Application):
    """Main application class."""

    def __init__(self):
        super().__init__(
            application_id="org.frostyard.Kapsule.Settings",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = KapsuleWindow(application=self)
        win.present()


def main():
    app = KapsuleApp()
    return app.run(sys.argv)
