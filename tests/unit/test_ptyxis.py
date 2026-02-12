"""Tests for Ptyxis profile management."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_gio():
    """Mock Gio and GLib for Ptyxis when gi is not installed."""
    mock_gio_mod = MagicMock()
    mock_glib_mod = MagicMock()

    settings = MagicMock()
    settings.get_value.return_value = MagicMock()
    settings.get_value.return_value.unpack.return_value = []
    mock_gio_mod.Settings.new_with_path.return_value = settings
    mock_gio_mod.Settings.new.return_value = settings

    with patch("kapsule.daemon.ptyxis.Gio", mock_gio_mod, create=True), \
         patch("kapsule.daemon.ptyxis.GLib", mock_glib_mod, create=True), \
         patch("kapsule.daemon.ptyxis.PTYXIS_AVAILABLE", True):
        yield mock_gio_mod


def test_create_profile_returns_uuid(mock_gio):
    from kapsule.daemon.ptyxis import create_ptyxis_profile

    uuid = create_ptyxis_profile("my-dev")
    assert uuid is not None
    assert len(uuid) == 36  # UUID format


def test_delete_profile(mock_gio):
    from kapsule.daemon.ptyxis import create_ptyxis_profile, delete_ptyxis_profile

    uuid = create_ptyxis_profile("my-dev")
    delete_ptyxis_profile(uuid)
    # Should not raise


def test_ptyxis_not_installed_returns_none():
    with patch("kapsule.daemon.ptyxis.PTYXIS_AVAILABLE", False):
        from kapsule.daemon.ptyxis import create_ptyxis_profile

        result = create_ptyxis_profile("my-dev")
        assert result is None
