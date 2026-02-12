"""Tests for the kapsule CLI."""

import pytest
from unittest.mock import AsyncMock, patch
from typer.testing import CliRunner

from kapsule.cli.app import app


runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_client():
    """Mock KapsuleClient for all CLI tests."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch("kapsule.cli.app.KapsuleClient", return_value=client):
        yield client


def test_list_containers(mock_client):
    mock_client.list_containers.return_value = [
        {"name": "dev", "status": "Running", "image": "images:ubuntu/24.04",
         "created": "2026-01-01", "mode": "default"},
        {"name": "test", "status": "Stopped", "image": "images:archlinux",
         "created": "2026-01-02", "mode": "default"},
    ]

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "dev" in result.output
    assert "Running" in result.output


def test_list_hides_stopped_by_default(mock_client):
    mock_client.list_containers.return_value = [
        {"name": "dev", "status": "Running", "image": "images:ubuntu/24.04",
         "created": "2026-01-01", "mode": "default"},
        {"name": "test", "status": "Stopped", "image": "images:archlinux",
         "created": "2026-01-02", "mode": "default"},
    ]

    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "dev" in result.output
    assert "test" not in result.output


def test_list_all_shows_stopped(mock_client):
    mock_client.list_containers.return_value = [
        {"name": "dev", "status": "Running", "image": "images:ubuntu/24.04",
         "created": "2026-01-01", "mode": "default"},
        {"name": "test", "status": "Stopped", "image": "images:archlinux",
         "created": "2026-01-02", "mode": "default"},
    ]

    result = runner.invoke(app, ["list", "--all"])
    assert result.exit_code == 0
    assert "dev" in result.output
    assert "test" in result.output


def test_create_container(mock_client):
    mock_client.create_container.return_value = "/org/frostyard/Kapsule/operations/1"

    result = runner.invoke(app, ["create", "my-dev", "--image", "images:ubuntu/24.04"])
    assert result.exit_code == 0
    mock_client.create_container.assert_called_once()


def test_rm_container(mock_client):
    mock_client.delete_container.return_value = "/org/frostyard/Kapsule/operations/2"

    result = runner.invoke(app, ["rm", "my-dev"])
    assert result.exit_code == 0
    mock_client.delete_container.assert_called_once()


def test_start_container(mock_client):
    mock_client.start_container.return_value = "/org/frostyard/Kapsule/operations/3"

    result = runner.invoke(app, ["start", "my-dev"])
    assert result.exit_code == 0
    mock_client.start_container.assert_called_once()


def test_stop_container(mock_client):
    mock_client.stop_container.return_value = "/org/frostyard/Kapsule/operations/4"

    result = runner.invoke(app, ["stop", "my-dev"])
    assert result.exit_code == 0
    mock_client.stop_container.assert_called_once()


def test_config_shows_all(mock_client):
    mock_client.get_config.return_value = {
        "default_container": "dev",
        "default_image": "images:archlinux",
    }

    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "default_container" in result.output
    assert "dev" in result.output
