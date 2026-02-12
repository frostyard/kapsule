"""Tests for the kapsule D-Bus client library."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kapsule.client import KapsuleClient
from kapsule.client.exceptions import DaemonNotRunning


BUS_NAME = "org.frostyard.Kapsule"
OBJ_PATH = "/org/frostyard/Kapsule"
IFACE = "org.frostyard.Kapsule.Manager"


@pytest.fixture
def mock_iface():
    return AsyncMock()


@pytest.fixture
def mock_proxy(mock_iface):
    # get_interface is synchronous in dbus-fast, so use MagicMock
    proxy = MagicMock()
    proxy.get_interface.return_value = mock_iface
    return proxy


@pytest.fixture
def mock_bus(mock_proxy):
    bus = MagicMock()
    bus.connected = True
    bus.introspect = AsyncMock(return_value=MagicMock())
    bus.get_proxy_object = MagicMock(return_value=mock_proxy)
    bus.disconnect = MagicMock()
    return bus


@pytest.mark.asyncio
async def test_connect_creates_bus(mock_bus):
    with patch("kapsule.client.client.MessageBus") as MockBus:
        MockBus.return_value.connect = AsyncMock(return_value=mock_bus)

        async with KapsuleClient() as client:
            assert client._bus is not None


@pytest.mark.asyncio
async def test_list_containers(mock_bus, mock_iface):
    mock_iface.call_list_containers = AsyncMock(return_value=[
        ("dev", "Running", "images:ubuntu/24.04", "2026-01-01", "default"),
        ("test", "Stopped", "images:archlinux", "2026-01-02", "default"),
    ])

    with patch("kapsule.client.client.MessageBus") as MockBus:
        MockBus.return_value.connect = AsyncMock(return_value=mock_bus)

        async with KapsuleClient() as client:
            containers = await client.list_containers()
            assert len(containers) == 2
            assert containers[0]["name"] == "dev"
            assert containers[0]["status"] == "Running"
            assert containers[1]["name"] == "test"


@pytest.mark.asyncio
async def test_create_container(mock_bus, mock_iface):
    mock_iface.call_create_container = AsyncMock(
        return_value="/org/frostyard/Kapsule/operations/1"
    )

    with patch("kapsule.client.client.MessageBus") as MockBus:
        MockBus.return_value.connect = AsyncMock(return_value=mock_bus)

        async with KapsuleClient() as client:
            op_path = await client.create_container("dev", image="images:ubuntu/24.04")
            mock_iface.call_create_container.assert_called_once()
            assert op_path == "/org/frostyard/Kapsule/operations/1"


@pytest.mark.asyncio
async def test_daemon_not_running():
    with patch("kapsule.client.client.MessageBus") as MockBus:
        MockBus.return_value.connect = AsyncMock(
            side_effect=ConnectionError("Connection refused")
        )
        with pytest.raises(DaemonNotRunning):
            async with KapsuleClient():
                pass
