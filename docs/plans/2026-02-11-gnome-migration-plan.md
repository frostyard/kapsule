# GNOME Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace all KDE/Qt/C++ components with GNOME/GTK/Python equivalents, keeping the Python D-Bus daemon as the stable core.

**Architecture:** Python D-Bus daemon (unchanged) exposes `org.frostyard.Kapsule` on the system bus. A new Python client library wraps this D-Bus API. A typer CLI, Ptyxis profile manager, GNOME Shell extension (GJS), Nautilus extension, and GTK4 settings app all consume the same D-Bus interface.

**Tech Stack:** Python 3.11+, dbus-fast, typer, rich, PyGObject, GTK4, libadwaita, GJS

**Design doc:** `docs/plans/2026-02-11-gnome-migration-design.md`

---

## Task 1: Rename D-Bus Namespace

Rename `org.kde.kapsule` to `org.frostyard.Kapsule` and `/org/kde/kapsule` to `/org/frostyard/Kapsule` across the entire codebase.

**Files:**
- Modify: `src/daemon/service.py` (lines 7, 46, 58, 72, 471, 483, 487, 488)
- Modify: `src/daemon/operations.py` (lines 84, 88, 100)
- Modify: `data/dbus/system/org.kde.kapsule.service` → rename to `data/dbus/system/org.frostyard.Kapsule.service`
- Modify: `data/dbus/system/org.kde.kapsule.conf` → rename to `data/dbus/system/org.frostyard.Kapsule.conf`
- Modify: `data/systemd/system/kapsule-daemon.service` (line 15)
- Modify: `docs/ARCHITECTURE.md`
- Modify: `tests/integration/helpers.sh`
- Modify: `tests/integration/run-tests.sh`
- Modify: `tests/integration/test_progress_signals.py`

**Step 1: Update daemon service.py**

Replace all occurrences of `org.kde.kapsule` with `org.frostyard.Kapsule` and `/org/kde/kapsule` with `/org/frostyard/Kapsule`:

```python
# service.py line 58
super().__init__("org.frostyard.Kapsule.Manager")

# service.py line 471
self._bus.export("/org/frostyard/Kapsule", self._interface)

# service.py line 483
await self._bus.request_name("org.frostyard.Kapsule")
```

**Step 2: Update daemon operations.py**

```python
# operations.py line 88
super().__init__("org.frostyard.Kapsule.Operation")

# operations.py line 100
return f"/org/frostyard/Kapsule/operations/{self._op_id}"
```

**Step 3: Rename and update D-Bus system files**

Rename `data/dbus/system/org.kde.kapsule.service` → `data/dbus/system/org.frostyard.Kapsule.service` and update contents:
```ini
Name=org.frostyard.Kapsule
```

Rename `data/dbus/system/org.kde.kapsule.conf` → `data/dbus/system/org.frostyard.Kapsule.conf` and replace all `org.kde.kapsule` with `org.frostyard.Kapsule`.

**Step 4: Update systemd service**

In `data/systemd/system/kapsule-daemon.service`:
```ini
BusName=org.frostyard.Kapsule
```

**Step 5: Update integration tests**

Replace `org.kde.kapsule` with `org.frostyard.Kapsule` and `/org/kde/kapsule` with `/org/frostyard/Kapsule` in:
- `tests/integration/helpers.sh`
- `tests/integration/run-tests.sh`
- `tests/integration/test_progress_signals.py`

**Step 6: Update docs/ARCHITECTURE.md**

Replace all `org.kde.kapsule` references with `org.frostyard.Kapsule`.

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: rename D-Bus namespace from org.kde.kapsule to org.frostyard.Kapsule"
```

---

## Task 2: Remove C++/Qt/KDE Code and CMake Build System

Remove all C++ source, Qt/KDE library, and CMake infrastructure. The project becomes pure Python.

**Files:**
- Delete: `src/cli/main.cpp`
- Delete: `src/cli/output.cpp`
- Delete: `src/cli/output.h`
- Delete: `src/cli/rang.hpp`
- Delete: `src/cli/CMakeLists.txt`
- Delete: `src/libkapsule-qt/` (entire directory)
- Delete: `CMakeLists.txt`
- Delete: `src/CMakeLists.txt` (if exists)
- Modify: `pyproject.toml` — update metadata, remove KDE references

**Step 1: Delete C++ CLI**

```bash
rm -rf src/cli/
```

**Step 2: Delete Qt library**

```bash
rm -rf src/libkapsule-qt/
```

**Step 3: Delete CMake files**

```bash
rm -f CMakeLists.txt
```

Check for any other CMakeLists.txt files in subdirectories and remove them.

**Step 4: Update pyproject.toml**

Replace the full file. Key changes:
- Description: remove "KDE", add "GNOME"
- Authors: update to frostyard
- Keywords: replace "kde" with "gnome"
- URLs: update to frostyard repos
- Remove broken `[tool.setuptools]` section that pointed at C++ src/cli
- Add proper package discovery for Python source

```toml
[project]
name = "kapsule"
version = "0.1.0"
description = "Incus-based container management with GNOME integration"
readme = "README.md"
license = "GPL-3.0-or-later"
requires-python = ">=3.11"
authors = [
    {name = "Frostyard"}
]
keywords = ["containers", "incus", "lxc", "gnome", "distrobox", "development"]

dependencies = [
    "httpx>=0.25.0",
    "dbus-fast>=4.0.0",
    "typer[all]>=0.9.0",
    "rich>=13.0.0",
    "pyyaml>=6.0",
    "pydantic>=2.0",
]

[project.scripts]
kapsule = "kapsule.cli:app"
kap = "kapsule.cli:app"
kapsule-daemon = "kapsule.daemon.__main__:main"

[tool.setuptools.packages.find]
where = ["src"]
include = ["kapsule*"]

[tool.setuptools.package-dir]
kapsule = "src"
```

**Step 5: Update .gitignore**

Remove `compile_commands.json` (CMake artifact). Add `build/`, `dist/`.

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: remove C++/Qt/KDE code and CMake build system

Drop src/cli/ (C++ CLI), src/libkapsule-qt/ (Qt library), and
CMakeLists.txt. The project is now pure Python. Update pyproject.toml
with GNOME-oriented metadata and proper Python package discovery."
```

---

## Task 3: Restructure Python Source as a Package

The daemon currently lives at `src/daemon/`. We need to restructure so everything is importable as the `kapsule` package.

**Files:**
- Create: `src/kapsule/__init__.py`
- Create: `src/kapsule/client/__init__.py` (empty, placeholder)
- Create: `src/kapsule/cli/__init__.py` (empty, placeholder)
- Move: `src/daemon/` → `src/kapsule/daemon/`
- Update: `pyproject.toml` package discovery
- Update: `data/systemd/system/kapsule-daemon.service` ExecStart path
- Update: `data/dbus/system/org.frostyard.Kapsule.service` Exec path

**Step 1: Create package structure**

```bash
mkdir -p src/kapsule/client src/kapsule/cli
touch src/kapsule/__init__.py src/kapsule/client/__init__.py src/kapsule/cli/__init__.py
mv src/daemon/* src/kapsule/daemon/
# Create daemon __init__.py if missing
touch src/kapsule/daemon/__init__.py
rmdir src/daemon
```

**Step 2: Update internal imports in daemon files**

Search all files in `src/kapsule/daemon/` for relative imports like `from .service import` etc. These should still work since we moved the whole directory. Verify by checking `__main__.py` imports.

**Step 3: Update pyproject.toml**

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["kapsule*"]
```

**Step 4: Update systemd service ExecStart**

In `data/systemd/system/kapsule-daemon.service`, update the ExecStart to use the new module path:
```ini
ExecStart=/usr/bin/python3 -m kapsule.daemon
```

**Step 5: Update D-Bus service Exec**

In `data/dbus/system/org.frostyard.Kapsule.service`:
```ini
Exec=/usr/bin/python3 -m kapsule.daemon
```

**Step 6: Verify daemon still imports cleanly**

```bash
cd src && python3 -c "from kapsule.daemon.service import KapsuleManagerInterface; print('OK')"
```

**Step 7: Commit**

```bash
git add -A
git commit -m "refactor: restructure source as kapsule Python package

Move src/daemon/ to src/kapsule/daemon/. Create package structure
with placeholders for client and cli subpackages. Update systemd
and D-Bus service files for new module path."
```

---

## Task 4: Create Python Client Library

A thin async wrapper around the daemon's D-Bus API using dbus-fast.

**Files:**
- Create: `src/kapsule/client/__init__.py`
- Create: `src/kapsule/client/client.py`
- Create: `src/kapsule/client/exceptions.py`
- Create: `tests/unit/test_client.py`

**Step 1: Write client exceptions**

Create `src/kapsule/client/exceptions.py`:

```python
"""Kapsule client exceptions."""


class KapsuleError(Exception):
    """Base exception for kapsule client errors."""


class DaemonNotRunning(KapsuleError):
    """The kapsule daemon is not running."""

    def __init__(self):
        super().__init__(
            "kapsule daemon is not running. "
            "Start it with: sudo systemctl start kapsule-daemon"
        )


class ContainerNotFound(KapsuleError):
    """The requested container does not exist."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"container not found: {name}")


class ContainerError(KapsuleError):
    """An operation on a container failed."""

    def __init__(self, message: str):
        super().__init__(message)
```

**Step 2: Write the failing tests**

Create `tests/unit/test_client.py`:

```python
"""Tests for the kapsule D-Bus client library."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kapsule.client import KapsuleClient
from kapsule.client.exceptions import DaemonNotRunning


BUS_NAME = "org.frostyard.Kapsule"
OBJ_PATH = "/org/frostyard/Kapsule"
IFACE = "org.frostyard.Kapsule.Manager"


@pytest.fixture
def mock_bus():
    bus = AsyncMock()
    bus.connected = True
    return bus


@pytest.fixture
def mock_proxy():
    proxy = AsyncMock()
    proxy.get_interface.return_value = AsyncMock()
    return proxy


@pytest.mark.asyncio
async def test_connect_creates_bus(mock_bus, mock_proxy):
    with patch("kapsule.client.client.MessageBus") as MockBus:
        MockBus.return_value.connect = AsyncMock(return_value=mock_bus)
        mock_bus.get_proxy_object = AsyncMock(return_value=mock_proxy)

        async with KapsuleClient() as client:
            assert client._bus is not None


@pytest.mark.asyncio
async def test_list_containers(mock_bus, mock_proxy):
    iface = AsyncMock()
    iface.call_list_containers = AsyncMock(return_value=[
        ("dev", "Running", "images:ubuntu/24.04", "2026-01-01", "default"),
        ("test", "Stopped", "images:archlinux", "2026-01-02", "default"),
    ])
    mock_proxy.get_interface.return_value = iface

    with patch("kapsule.client.client.MessageBus") as MockBus:
        MockBus.return_value.connect = AsyncMock(return_value=mock_bus)
        mock_bus.get_proxy_object = AsyncMock(return_value=mock_proxy)

        async with KapsuleClient() as client:
            containers = await client.list_containers()
            assert len(containers) == 2
            assert containers[0]["name"] == "dev"
            assert containers[0]["status"] == "Running"
            assert containers[1]["name"] == "test"


@pytest.mark.asyncio
async def test_create_container(mock_bus, mock_proxy):
    iface = AsyncMock()
    iface.call_create_container = AsyncMock(
        return_value="/org/frostyard/Kapsule/operations/1"
    )
    mock_proxy.get_interface.return_value = iface

    with patch("kapsule.client.client.MessageBus") as MockBus:
        MockBus.return_value.connect = AsyncMock(return_value=mock_bus)
        mock_bus.get_proxy_object = AsyncMock(return_value=mock_proxy)

        async with KapsuleClient() as client:
            op_path = await client.create_container("dev", image="images:ubuntu/24.04")
            iface.call_create_container.assert_called_once()
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
```

**Step 3: Run tests to verify they fail**

```bash
cd /path/to/worktree
python3 -m pytest tests/unit/test_client.py -v
```

Expected: FAIL — `kapsule.client` module doesn't exist yet.

**Step 4: Implement the client**

Create `src/kapsule/client/client.py`:

```python
"""Async D-Bus client for the kapsule daemon."""

from __future__ import annotations

from dbus_fast.aio import MessageBus
from dbus_fast import BusType

from .exceptions import DaemonNotRunning, ContainerError


BUS_NAME = "org.frostyard.Kapsule"
OBJ_PATH = "/org/frostyard/Kapsule"
MANAGER_IFACE = "org.frostyard.Kapsule.Manager"


class KapsuleClient:
    """Async client for the kapsule D-Bus daemon.

    Usage:
        async with KapsuleClient() as client:
            containers = await client.list_containers()
    """

    def __init__(self):
        self._bus: MessageBus | None = None
        self._iface = None

    async def __aenter__(self):
        try:
            self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        except Exception as e:
            raise DaemonNotRunning() from e

        proxy = await self._bus.get_proxy_object(
            BUS_NAME, OBJ_PATH,
        )
        self._iface = proxy.get_interface(MANAGER_IFACE)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._bus:
            self._bus.disconnect()
        return False

    async def list_containers(self) -> list[dict]:
        """List all containers.

        Returns list of dicts with keys: name, status, image, created, mode.
        """
        raw = await self._iface.call_list_containers()
        return [
            {
                "name": c[0],
                "status": c[1],
                "image": c[2],
                "created": c[3],
                "mode": c[4],
            }
            for c in raw
        ]

    async def get_container_info(self, name: str) -> dict:
        """Get info for a single container."""
        raw = await self._iface.call_get_container_info(name)
        return {
            "name": raw[0],
            "status": raw[1],
            "image": raw[2],
            "created": raw[3],
            "mode": raw[4],
        }

    async def create_container(
        self,
        name: str,
        *,
        image: str = "",
        session_mode: bool = False,
        dbus_mux: bool = False,
    ) -> str:
        """Create a container. Returns operation D-Bus path."""
        return await self._iface.call_create_container(
            name, image, session_mode, dbus_mux
        )

    async def delete_container(self, name: str, *, force: bool = False) -> str:
        """Delete a container. Returns operation D-Bus path."""
        return await self._iface.call_delete_container(name, force)

    async def start_container(self, name: str) -> str:
        """Start a container. Returns operation D-Bus path."""
        return await self._iface.call_start_container(name)

    async def stop_container(self, name: str, *, force: bool = False) -> str:
        """Stop a container. Returns operation D-Bus path."""
        return await self._iface.call_stop_container(name, force)

    async def prepare_enter(
        self, container_name: str, command: list[str] | None = None
    ) -> tuple[bool, str, list[str]]:
        """Prepare to enter a container.

        Returns (success, message, exec_args).
        """
        result = await self._iface.call_prepare_enter(
            container_name, command or []
        )
        return (result[0], result[1], result[2])

    async def get_config(self) -> dict[str, str]:
        """Get daemon configuration."""
        return await self._iface.call_get_config()

    async def get_version(self) -> str:
        """Get daemon version."""
        return await self._iface.get_version()
```

**Step 5: Update client __init__.py**

```python
"""Kapsule D-Bus client library."""

from .client import KapsuleClient
from .exceptions import (
    KapsuleError,
    DaemonNotRunning,
    ContainerNotFound,
    ContainerError,
)

__all__ = [
    "KapsuleClient",
    "KapsuleError",
    "DaemonNotRunning",
    "ContainerNotFound",
    "ContainerError",
]
```

**Step 6: Run tests to verify they pass**

```bash
python3 -m pytest tests/unit/test_client.py -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add src/kapsule/client/ tests/unit/
git commit -m "feat: add Python D-Bus client library

Async client wrapping org.frostyard.Kapsule.Manager interface.
Supports all daemon operations: create, delete, start, stop,
enter, list, config. Includes exception hierarchy and unit tests."
```

---

## Task 5: Create Python CLI

Replace the C++ CLI with a Python typer CLI that uses the client library.

**Files:**
- Create: `src/kapsule/cli/__init__.py`
- Create: `src/kapsule/cli/app.py`
- Create: `src/kapsule/cli/output.py`
- Create: `tests/unit/test_cli.py`

**Step 1: Write failing tests for the CLI**

Create `tests/unit/test_cli.py`:

```python
"""Tests for the kapsule CLI."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typer.testing import CliRunner

from kapsule.cli.app import app


runner = CliRunner()


@pytest.fixture(autouse=True)
def mock_client():
    """Mock KapsuleClient for all CLI tests."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with patch("kapsule.cli.app.KapsuleClient", return_value=client) as mock:
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
```

**Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/unit/test_cli.py -v
```

Expected: FAIL — `kapsule.cli.app` doesn't exist.

**Step 3: Implement CLI output helpers**

Create `src/kapsule/cli/output.py`:

```python
"""CLI output formatting using rich."""

from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console()
err_console = Console(stderr=True)


STATUS_COLORS = {
    "Running": "green",
    "Stopped": "red",
    "Starting": "yellow",
    "Stopping": "yellow",
}


def print_error(message: str) -> None:
    err_console.print(f"[red]error:[/red] {message}")


def print_success(message: str) -> None:
    console.print(f"[green]{message}[/green]")


def print_containers(containers: list[dict], show_all: bool = False) -> None:
    if not show_all:
        containers = [c for c in containers if c["status"] == "Running"]

    if not containers:
        console.print("[dim]No containers running.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Image")

    for c in containers:
        color = STATUS_COLORS.get(c["status"], "white")
        table.add_row(c["name"], f"[{color}]{c['status']}[/{color}]", c["image"])

    console.print(table)
```

**Step 4: Implement the CLI app**

Create `src/kapsule/cli/app.py`:

```python
"""Kapsule CLI application."""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional

import typer
from rich.console import Console

from kapsule.client import KapsuleClient, DaemonNotRunning
from kapsule.cli.output import print_error, print_success, print_containers, console

app = typer.Typer(
    name="kapsule",
    help="Manage Incus containers with GNOME integration.",
    no_args_is_help=True,
)


def run_async(coro):
    """Run an async coroutine from sync typer commands."""
    return asyncio.get_event_loop().run_until_complete(coro)


def handle_errors(func):
    """Decorator to catch common client errors."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DaemonNotRunning as e:
            print_error(str(e))
            raise typer.Exit(1)
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1)
    # Preserve function metadata for typer
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    wrapper.__module__ = func.__module__
    wrapper.__wrapped__ = func
    # Copy typer parameter annotations
    import functools
    functools.update_wrapper(wrapper, func)
    return wrapper


@app.command()
@handle_errors
def create(
    name: str = typer.Argument(..., help="Container name"),
    image: str = typer.Option("", "--image", "-i", help="Image to use"),
    session_mode: bool = typer.Option(False, "--session", help="Enable session mode"),
    dbus_mux: bool = typer.Option(False, "--dbus-mux", help="Enable D-Bus multiplexing"),
):
    """Create a new container."""
    async def _create():
        async with KapsuleClient() as client:
            await client.create_container(
                name, image=image, session_mode=session_mode, dbus_mux=dbus_mux
            )
            print_success(f"Container '{name}' created.")

    run_async(_create())


@app.command("enter")
@handle_errors
def enter_container(
    name: str = typer.Argument(None, help="Container name (uses default if omitted)"),
):
    """Enter a container."""
    async def _enter():
        async with KapsuleClient() as client:
            container_name = name or ""
            success, message, exec_args = await client.prepare_enter(container_name)
            if not success:
                print_error(message)
                raise typer.Exit(1)
            os.execvp(exec_args[0], exec_args)

    run_async(_enter())


@app.command("list")
@handle_errors
def list_containers(
    all_: bool = typer.Option(False, "--all", "-a", help="Show stopped containers too"),
):
    """List containers."""
    async def _list():
        async with KapsuleClient() as client:
            containers = await client.list_containers()
            print_containers(containers, show_all=all_)

    run_async(_list())


# Alias: ls → list
app.command("ls", hidden=True)(list_containers)


@app.command()
@handle_errors
def start(
    name: str = typer.Argument(..., help="Container name"),
):
    """Start a container."""
    async def _start():
        async with KapsuleClient() as client:
            await client.start_container(name)
            print_success(f"Container '{name}' started.")

    run_async(_start())


@app.command()
@handle_errors
def stop(
    name: str = typer.Argument(..., help="Container name"),
    force: bool = typer.Option(False, "--force", "-f", help="Force stop"),
):
    """Stop a container."""
    async def _stop():
        async with KapsuleClient() as client:
            await client.stop_container(name, force=force)
            print_success(f"Container '{name}' stopped.")

    run_async(_stop())


@app.command()
@handle_errors
def rm(
    name: str = typer.Argument(..., help="Container name"),
    force: bool = typer.Option(False, "--force", "-f", help="Force removal"),
):
    """Remove a container."""
    async def _rm():
        async with KapsuleClient() as client:
            await client.delete_container(name, force=force)
            print_success(f"Container '{name}' removed.")

    run_async(_rm())


# Alias: remove → rm
app.command("remove", hidden=True)(rm)


@app.command()
@handle_errors
def config(
    key: Optional[str] = typer.Argument(None, help="Config key to show"),
):
    """Show configuration."""
    async def _config():
        async with KapsuleClient() as client:
            cfg = await client.get_config()
            if key:
                if key in cfg:
                    console.print(cfg[key])
                else:
                    print_error(f"unknown config key: {key}")
                    raise typer.Exit(1)
            else:
                for k, v in cfg.items():
                    console.print(f"[bold]{k}[/bold] = {v}")

    run_async(_config())
```

**Step 5: Update cli __init__.py**

```python
"""Kapsule CLI."""

from .app import app

__all__ = ["app"]
```

**Step 6: Run tests to verify they pass**

```bash
python3 -m pytest tests/unit/test_cli.py -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add src/kapsule/cli/ tests/unit/test_cli.py
git commit -m "feat: add Python CLI replacing C++ version

Implements all commands: create, enter, list/ls, start, stop, rm/remove,
config. Uses typer for argument parsing, rich for output formatting.
Thin layer over the kapsule.client library. Includes unit tests."
```

---

## Task 6: Update README and Documentation

Update README.md and ARCHITECTURE.md to reflect the GNOME orientation.

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`

**Step 1: Update README.md**

Replace KDE/Plasma references with GNOME. Update:
- Title/description: "GNOME integration" instead of "KDE/Plasma integration"
- Dependencies: Python, GTK4, libadwaita instead of Qt6, KF6
- Build instructions: pip/pyproject.toml instead of CMake
- Planned features: Shell extension, Nautilus, Ptyxis, Settings app

**Step 2: Update ARCHITECTURE.md**

Replace the three-tier diagram. Remove Qt library tier. Update:
- Architecture diagram with new Python-only stack
- D-Bus interface section with `org.frostyard.Kapsule`
- Component descriptions
- Remove CMake build sections

**Step 3: Commit**

```bash
git add README.md docs/ARCHITECTURE.md
git commit -m "docs: update README and architecture for GNOME migration"
```

---

## Task 7: Ptyxis Profile Integration

Add automatic Ptyxis terminal profile creation/deletion when containers are created/deleted.

**Files:**
- Create: `src/kapsule/daemon/ptyxis.py`
- Create: `tests/unit/test_ptyxis.py`
- Modify: `src/kapsule/daemon/container_service.py`

**Step 1: Write failing tests**

Create `tests/unit/test_ptyxis.py`:

```python
"""Tests for Ptyxis profile management."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_gio():
    """Mock Gio.Settings for Ptyxis."""
    with patch("kapsule.daemon.ptyxis.Gio") as mock:
        settings = MagicMock()
        settings.get_value.return_value = MagicMock()
        settings.get_value.return_value.unpack.return_value = []
        mock.Settings.new_with_path.return_value = settings
        mock.Settings.new.return_value = settings
        yield mock


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
```

**Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/unit/test_ptyxis.py -v
```

**Step 3: Implement Ptyxis profile manager**

Create `src/kapsule/daemon/ptyxis.py`:

```python
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
```

**Step 4: Hook into container_service.py**

In `src/kapsule/daemon/container_service.py`, after a container is successfully created, call `create_ptyxis_profile(name)`. After deletion, call `delete_ptyxis_profile(uuid)`. Store the profile UUID in the container's metadata (Incus `user.kapsule.ptyxis-profile` config key).

Add near end of `create_container` method (after container is running):
```python
from kapsule.daemon.ptyxis import create_ptyxis_profile
profile_uuid = create_ptyxis_profile(name)
if profile_uuid:
    # Store UUID in container metadata for cleanup
    await self._client.update_container_config(
        name, {"user.kapsule.ptyxis-profile": profile_uuid}
    )
```

Add near end of `delete_container` method (before container is deleted):
```python
from kapsule.daemon.ptyxis import delete_ptyxis_profile
info = await self._client.get_container(name)
profile_uuid = info.get("config", {}).get("user.kapsule.ptyxis-profile")
if profile_uuid:
    delete_ptyxis_profile(profile_uuid)
```

**Step 5: Run tests**

```bash
python3 -m pytest tests/unit/test_ptyxis.py -v
```

**Step 6: Commit**

```bash
git add src/kapsule/daemon/ptyxis.py tests/unit/test_ptyxis.py src/kapsule/daemon/container_service.py
git commit -m "feat: auto-create Ptyxis terminal profiles for containers

When a container is created, a matching Ptyxis profile is created
with a custom command to enter it. Profile UUID stored in container
metadata for cleanup on deletion. No-op if Ptyxis is not installed."
```

---

## Task 8: GNOME Shell Extension

Create the GJS Shell extension for the GNOME top bar.

**Files:**
- Create: `src/gnome/shell-extension/extension.js`
- Create: `src/gnome/shell-extension/metadata.json`
- Create: `src/gnome/shell-extension/stylesheet.css`

**Step 1: Create metadata.json**

```json
{
    "uuid": "kapsule@frostyard.org",
    "name": "Kapsule",
    "description": "Quick access to Kapsule containers",
    "shell-version": ["45", "46", "47"],
    "version": 1,
    "url": ""
}
```

**Step 2: Create stylesheet.css**

```css
.kapsule-container-item {
    padding: 4px 8px;
}

.kapsule-status-running {
    color: #57e389;
}

.kapsule-status-stopped {
    color: #ff7b63;
}
```

**Step 3: Create extension.js**

```javascript
import GObject from "gi://GObject";
import St from "gi://St";
import Gio from "gi://Gio";
import GLib from "gi://GLib";

import * as Main from "resource:///org/gnome/shell/ui/main.js";
import * as PanelMenu from "resource:///org/gnome/shell/ui/panelMenu.js";
import * as PopupMenu from "resource:///org/gnome/shell/ui/popupMenu.js";

const BUS_NAME = "org.frostyard.Kapsule";
const OBJ_PATH = "/org/frostyard/Kapsule";
const IFACE_NAME = "org.frostyard.Kapsule.Manager";

const ManagerIface = `
<node>
  <interface name="${IFACE_NAME}">
    <method name="ListContainers">
      <arg direction="out" type="a(sssss)" name="containers"/>
    </method>
    <method name="StartContainer">
      <arg direction="in" type="s" name="name"/>
      <arg direction="out" type="o" name="operation"/>
    </method>
    <method name="StopContainer">
      <arg direction="in" type="s" name="name"/>
      <arg direction="in" type="b" name="force"/>
      <arg direction="out" type="o" name="operation"/>
    </method>
  </interface>
</node>
`;

const ManagerProxy = Gio.DBusProxy.makeProxyWrapper(ManagerIface);

const KapsuleIndicator = GObject.registerClass(
class KapsuleIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, "Kapsule");

        this._icon = new St.Icon({
            icon_name: "utilities-terminal-symbolic",
            style_class: "system-status-icon",
        });
        this.add_child(this._icon);

        this._proxy = null;
        this._buildMenu();
        this._connectProxy();
    }

    _connectProxy() {
        try {
            this._proxy = new ManagerProxy(
                Gio.DBus.system,
                BUS_NAME,
                OBJ_PATH
            );
        } catch (e) {
            log(`Kapsule: Failed to connect to daemon: ${e.message}`);
        }
    }

    _buildMenu() {
        this.menu.removeAll();
        this._loadingItem = new PopupMenu.PopupMenuItem("Loading...", {
            reactive: false,
        });
        this.menu.addMenuItem(this._loadingItem);
    }

    _onOpenStateChanged(menu, open) {
        super._onOpenStateChanged(menu, open);
        if (open) this._refresh();
    }

    _refresh() {
        if (!this._proxy) {
            this.menu.removeAll();
            this.menu.addMenuItem(
                new PopupMenu.PopupMenuItem("Daemon not running", {
                    reactive: false,
                })
            );
            return;
        }

        this._proxy.ListContainersRemote((result, error) => {
            this.menu.removeAll();

            if (error) {
                this.menu.addMenuItem(
                    new PopupMenu.PopupMenuItem(`Error: ${error.message}`, {
                        reactive: false,
                    })
                );
                return;
            }

            const containers = result[0];
            if (containers.length === 0) {
                this.menu.addMenuItem(
                    new PopupMenu.PopupMenuItem("No containers", {
                        reactive: false,
                    })
                );
                return;
            }

            for (const [name, status, image, created, mode] of containers) {
                const running = status === "Running";
                const label = `${name}  ${running ? "●" : "○"}`;
                const item = new PopupMenu.PopupMenuItem(label);

                if (running) {
                    item.connect("activate", () => {
                        GLib.spawn_command_line_async(
                            `ptyxis --tab-with-profile-name=${name}`
                        );
                    });
                } else {
                    item.connect("activate", () => {
                        this._proxy.StartContainerRemote(name, () => {});
                    });
                }

                this.menu.addMenuItem(item);
            }

            this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

            const settingsItem = new PopupMenu.PopupMenuItem("Open Kapsule Settings");
            settingsItem.connect("activate", () => {
                GLib.spawn_command_line_async("kapsule-settings");
            });
            this.menu.addMenuItem(settingsItem);
        });
    }

    destroy() {
        this._proxy = null;
        super.destroy();
    }
});

export default class KapsuleExtension {
    constructor(metadata) {
        this._metadata = metadata;
    }

    enable() {
        this._indicator = new KapsuleIndicator();
        Main.panel.addToStatusArea("kapsule", this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
```

**Step 4: Commit**

```bash
git add src/gnome/shell-extension/
git commit -m "feat: add GNOME Shell extension for container quick-access

Top bar indicator showing container list with status. Click running
containers to open Ptyxis, click stopped containers to start them.
Settings app launcher in the menu."
```

---

## Task 9: Nautilus Extension

Create the Nautilus right-click menu extension.

**Files:**
- Create: `src/gnome/nautilus/kapsule-nautilus.py`

**Step 1: Create the extension**

```python
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
```

**Step 2: Commit**

```bash
git add src/gnome/nautilus/
git commit -m "feat: add Nautilus extension for container terminal access

Right-click 'Open Terminal in Container' submenu listing running
containers. Opens Ptyxis with the container's profile."
```

---

## Task 10: GTK4 Settings App

Create the container management GUI.

**Files:**
- Create: `src/kapsule/gnome/__init__.py`
- Create: `src/kapsule/gnome/settings/__init__.py`
- Create: `src/kapsule/gnome/settings/app.py`
- Create: `src/kapsule/gnome/settings/window.py`
- Create: `src/kapsule/gnome/settings/container_row.py`
- Create: `src/kapsule/gnome/settings/create_dialog.py`
- Create: `data/applications/org.frostyard.Kapsule.desktop`

This is the largest task. Build it incrementally.

**Step 1: Create .desktop file**

Create `data/applications/org.frostyard.Kapsule.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=Kapsule
Comment=Manage containers
Exec=kapsule-settings
Icon=utilities-terminal
Categories=System;
Keywords=containers;incus;
```

**Step 2: Create the app entry point**

Create `src/kapsule/gnome/__init__.py` (empty).
Create `src/kapsule/gnome/settings/__init__.py` (empty).

Create `src/kapsule/gnome/settings/app.py`:

```python
"""Kapsule Settings GTK4/libadwaita application."""

from __future__ import annotations

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

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
```

**Step 3: Create the main window**

Create `src/kapsule/gnome/settings/window.py`:

```python
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

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(header)
        box.append(clamp)

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
        dialog = CreateDialog(transient_for=self, on_created=self._refresh)
        dialog.present()

    def _show_daemon_error(self):
        self._show_toast("Daemon not running. Start with: sudo systemctl start kapsule-daemon")

    def _show_toast(self, message):
        toast = Adw.Toast(title=message, timeout=5)
        # Find or create toast overlay
        self.get_application().props.active_window
```

**Step 4: Create container row widget**

Create `src/kapsule/gnome/settings/container_row.py`:

```python
"""Container list row widget."""

from __future__ import annotations

import asyncio
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

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
            enter_btn = Gtk.Button(icon_name="utilities-terminal-symbolic",
                                   valign=Gtk.Align.CENTER, tooltip_text="Enter")
            enter_btn.connect("clicked", self._on_enter)
            self.add_suffix(enter_btn)

            stop_btn = Gtk.Button(icon_name="media-playback-stop-symbolic",
                                  valign=Gtk.Align.CENTER, tooltip_text="Stop")
            stop_btn.add_css_class("destructive-action")
            stop_btn.connect("clicked", self._on_stop)
            self.add_suffix(stop_btn)
        else:
            start_btn = Gtk.Button(icon_name="media-playback-start-symbolic",
                                   valign=Gtk.Align.CENTER, tooltip_text="Start")
            start_btn.connect("clicked", self._on_start)
            self.add_suffix(start_btn)

        delete_btn = Gtk.Button(icon_name="user-trash-symbolic",
                                valign=Gtk.Align.CENTER, tooltip_text="Delete")
        delete_btn.add_css_class("destructive-action")
        delete_btn.connect("clicked", self._on_delete)
        self.add_suffix(delete_btn)

    def _run_async(self, coro):
        def run():
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(coro)
                if self._on_action:
                    GLib.idle_add(self._on_action)
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
```

**Step 5: Create the create dialog**

Create `src/kapsule/gnome/settings/create_dialog.py`:

```python
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
            except Exception as e:
                GLib.idle_add(button.set_sensitive, True)
            finally:
                loop.close()

        threading.Thread(target=create, daemon=True).start()

    def _on_success(self):
        if self._on_created:
            self._on_created()
        self.close()
```

**Step 6: Add entry point to pyproject.toml**

Ensure pyproject.toml has:
```toml
[project.gui-scripts]
kapsule-settings = "kapsule.gnome.settings.app:main"
```

**Step 7: Commit**

```bash
git add src/kapsule/gnome/ data/applications/
git commit -m "feat: add GTK4/libadwaita settings app for container management

Main window with container list, start/stop/enter/delete actions,
and create dialog. Uses libadwaita for native GNOME look. Connects
to daemon over D-Bus. Desktop file for app grid integration."
```

---

## Task 11: Install Script

Create an install script for files that can't be handled by pip.

**Files:**
- Create: `scripts/install-gnome-extensions.sh`

**Step 1: Create install script**

```bash
#!/bin/bash
# Install GNOME Shell extension and Nautilus extension to user directories.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# GNOME Shell extension
SHELL_EXT_DIR="$HOME/.local/share/gnome-shell/extensions/kapsule@frostyard.org"
echo "Installing GNOME Shell extension to $SHELL_EXT_DIR"
mkdir -p "$SHELL_EXT_DIR"
cp "$PROJECT_DIR/src/gnome/shell-extension/"* "$SHELL_EXT_DIR/"

# Nautilus extension
NAUTILUS_EXT_DIR="$HOME/.local/share/nautilus-python/extensions"
echo "Installing Nautilus extension to $NAUTILUS_EXT_DIR"
mkdir -p "$NAUTILUS_EXT_DIR"
cp "$PROJECT_DIR/src/gnome/nautilus/kapsule-nautilus.py" "$NAUTILUS_EXT_DIR/"

# Desktop file
DESKTOP_DIR="$HOME/.local/share/applications"
echo "Installing desktop file to $DESKTOP_DIR"
mkdir -p "$DESKTOP_DIR"
cp "$PROJECT_DIR/data/applications/org.frostyard.Kapsule.desktop" "$DESKTOP_DIR/"

echo "Done. You may need to:"
echo "  - Restart GNOME Shell (log out/in) to load the Shell extension"
echo "  - Restart Nautilus (nautilus -q) to load the Nautilus extension"
```

**Step 2: Make executable**

```bash
chmod +x scripts/install-gnome-extensions.sh
```

**Step 3: Commit**

```bash
git add scripts/install-gnome-extensions.sh
git commit -m "feat: add install script for GNOME Shell and Nautilus extensions"
```

---

## Task 12: Final Cleanup and Verification

**Step 1: Remove any remaining KDE references**

Search the entire codebase for "kde", "KDE", "Qt", "KF6", "QCoro" and remove/update any remaining references.

```bash
grep -ri "kde\|qt6\|kf6\|qcoro" --include='*.py' --include='*.md' --include='*.toml' --include='*.sh' .
```

**Step 2: Verify Python package structure**

```bash
python3 -c "from kapsule.client import KapsuleClient; print('client OK')"
python3 -c "from kapsule.cli.app import app; print('cli OK')"
python3 -c "from kapsule.daemon.ptyxis import create_ptyxis_profile; print('ptyxis OK')"
```

**Step 3: Run all unit tests**

```bash
python3 -m pytest tests/unit/ -v
```

**Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final cleanup of KDE references"
```
