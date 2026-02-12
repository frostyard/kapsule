"""Ptyxis terminal profile management.

Creates and deletes Ptyxis profiles for kapsule containers.
If Ptyxis is not installed, all operations are no-ops.
"""

from __future__ import annotations

import uuid as uuid_mod
import logging

logger = logging.getLogger(__name__)

try:
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
    PTYXIS_AVAILABLE = True
except (ImportError, ValueError):
    PTYXIS_AVAILABLE = False


PTYXIS_SCHEMA = "org.gnome.Ptyxis"
PTYXIS_PROFILE_SCHEMA = "org.gnome.Ptyxis.Profile"
PTYXIS_PROFILE_PATH = "/org/gnome/Ptyxis/Profiles/"


def create_ptyxis_profile(container_name: str) -> str | None:
    """Create a Ptyxis profile for a container.

    Returns the profile UUID, or None if Ptyxis is not available.
    """
    if not PTYXIS_AVAILABLE:
        return None

    try:
        profile_uuid = str(uuid_mod.uuid4())
        path = f"{PTYXIS_PROFILE_PATH}{profile_uuid}/"

        profile = Gio.Settings.new_with_path(PTYXIS_PROFILE_SCHEMA, path)
        profile.set_string("label", container_name)
        profile.set_string("custom-command", f"kapsule enter {container_name}")
        profile.set_boolean("use-custom-command", True)

        # Add to profile list
        main = Gio.Settings.new(PTYXIS_SCHEMA)
        profiles = list(main.get_value("profile-uuids").unpack())
        profiles.append(profile_uuid)
        main.set_value("profile-uuids", GLib.Variant("as", profiles))

        logger.info("Created Ptyxis profile %s for container %s", profile_uuid, container_name)
        return profile_uuid
    except Exception:
        logger.debug("Failed to create Ptyxis profile for %s", container_name, exc_info=True)
        return None


def delete_ptyxis_profile(profile_uuid: str) -> None:
    """Delete a Ptyxis profile by UUID."""
    if not PTYXIS_AVAILABLE:
        return

    try:
        main = Gio.Settings.new(PTYXIS_SCHEMA)
        profiles = list(main.get_value("profile-uuids").unpack())
        if profile_uuid in profiles:
            profiles.remove(profile_uuid)
            main.set_value("profile-uuids", GLib.Variant("as", profiles))
        logger.info("Deleted Ptyxis profile %s", profile_uuid)
    except Exception:
        logger.debug("Failed to delete Ptyxis profile %s", profile_uuid, exc_info=True)
