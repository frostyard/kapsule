<!--
SPDX-FileCopyrightText: 2026 Frostyard

SPDX-License-Identifier: CC-BY-SA-4.0
-->

# Kapsule Architecture

Kapsule is an Incus-based container manager with native GNOME integration. It provides a distrobox-like experience with emphasis on nested containerization and seamless desktop integration.

## Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     User-Facing Components (Python/GJS)                      │
│                                                                              │
│   ┌─────────────────┐  ┌────────────────┐  ┌───────────────────────────────┐ │
│   │  kapsule CLI    │  │ GNOME Shell    │  │ Settings App (GTK4/Adwaita)  │ │
│   │  (typer/rich)   │  │ Extension      │  │                               │ │
│   └────────┬────────┘  └───────┬────────┘  └──────────────┬────────────────┘ │
│            │                   │                           │                  │
│            └───────────────────┼───────────────────────────┘                  │
│                                │                                             │
│                       ┌────────▼────────┐                                    │
│                       │ kapsule.client  │  ┌──────────────┐                  │
│                       │ (dbus-fast)     │  │ Nautilus Ext  │                  │
│                       └────────┬────────┘  └──────┬───────┘                  │
└────────────────────────────────┼──────────────────┼──────────────────────────┘
                                 │ D-Bus (system bus)
                                 │ org.frostyard.Kapsule
┌────────────────────────────────▼─────────────────────────────────────────────┐
│                        kapsule-daemon (Python)                               │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │ org.frostyard.Kapsule.Manager                                       │   │
│   │ ├── Properties: Version                                             │   │
│   │ └── Methods: CreateContainer, DeleteContainer, StartContainer, ...  │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │ org.frostyard.Kapsule.Operation (per-operation objects)              │   │
│   │ Path: /org/frostyard/Kapsule/operations/{id}                        │   │
│   │ ├── Properties: Id, Type, Description, Target, Status               │   │
│   │ ├── Signals: Message, ProgressStarted, ProgressUpdate, ...          │   │
│   │ └── Methods: Cancel                                                 │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌─────────────────┐    ┌─────────────────┐    ┌────────────────────────┐  │
│   │ ContainerService│──▶│  IncusClient    │    │  OperationTracker      │  │
│   │ (operations)    │    │  (REST client)  │    │  (D-Bus objects)       │  │
│   └─────────────────┘    └────────┬────────┘    └────────────────────────┘  │
└───────────────────────────────────┼──────────────────────────────────────────┘
                                    │ HTTP over Unix socket
                                    │ /var/lib/incus/unix.socket
┌───────────────────────────────────▼──────────────────────────────────────────┐
│                            Incus Daemon                                      │
│                    (container lifecycle, images, storage)                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Component Summary

| Component | Language | Purpose |
|-----------|----------|---------|
| `kapsule` CLI | Python (typer) | User-facing command-line interface |
| `kapsule.client` | Python | Async D-Bus client library |
| `kapsule-daemon` | Python | System service bridging D-Bus and Incus |
| GNOME Shell extension | GJS | Top bar container indicator |
| Nautilus extension | Python | Right-click menu integration |
| Settings app | Python (GTK4/Adw) | Container management GUI |
| Ptyxis integration | Python | Auto-create terminal profiles |

---

## kapsule-daemon (Python)

The daemon is the heart of Kapsule. It runs as a systemd system service (`kapsule-daemon.service`) and provides container management over D-Bus.

### Why Python?

- **Incus REST API** is trivial to consume with `httpx` async HTTP client
- **Fast iteration** during development
- **No CGO/native binding complexity** - pure HTTP over Unix socket
- **dbus-fast** provides excellent async D-Bus support with Cython acceleration

### Module Structure

```
src/kapsule/
├── __init__.py
├── daemon/
│   ├── __main__.py          # Entry point: python -m kapsule.daemon
│   ├── service.py           # KapsuleManagerInterface (D-Bus service)
│   ├── container_service.py # Container lifecycle operations
│   ├── operations.py        # @operation decorator, progress reporting
│   ├── incus_client.py      # Typed async Incus REST client
│   ├── ptyxis.py            # Ptyxis terminal profile management
│   ├── models_generated.py  # Pydantic models from Incus OpenAPI spec
│   ├── config.py            # User configuration handling
│   └── dbus_types.py        # D-Bus type annotations
├── client/
│   ├── __init__.py          # KapsuleClient, exceptions
│   ├── client.py            # Async D-Bus client
│   └── exceptions.py        # Exception hierarchy
└── cli/
    ├── __init__.py
    ├── app.py               # Typer CLI application
    └── output.py            # Rich output formatting
```

### D-Bus Interface Design

The daemon exposes two interface types:

#### Manager Interface (`org.frostyard.Kapsule.Manager`)

Singleton service at `/org/frostyard/Kapsule`:

```python
# Methods - return operation object path immediately
CreateContainer(name: str, image: str, ...) -> object_path
DeleteContainer(name: str, force: bool) -> object_path
StartContainer(name: str) -> object_path
StopContainer(name: str, force: bool) -> object_path

# Properties
Version: str
```

#### Operation Interface (`org.frostyard.Kapsule.Operation`)

Per-operation objects at `/org/frostyard/Kapsule/operations/{id}`:

```python
# Properties
Id: str          # Unique operation identifier
Type: str        # "create", "delete", "start", "stop", etc.
Target: str      # Usually container name
Status: str      # "running", "completed", "failed", "cancelled"

# Progress signals
Message(type: int, message: str, indent: int)
ProgressStarted(id, description, total, indent)
ProgressUpdate(id, current, rate)
ProgressCompleted(id, success, message)
Completed(success: bool, error_message: str)

# Methods
Cancel()
```

### Operation Decorator Pattern

All long-running operations use the `@operation` decorator:

```python
@operation(
    "create",
    description="Creating container: {name}",
    target_param="name",
)
async def create_container(
    self,
    progress: OperationReporter,  # Auto-injected
    *,
    name: str,
    image: str,
) -> None:
    progress.info(f"Image: {image}")
    # ... do work ...
    progress.success(f"Container '{name}' created")
```

The decorator:
1. Creates an `OperationInterface` D-Bus object
2. Exports it at `/org/frostyard/Kapsule/operations/{id}`
3. Returns the object path immediately to the caller
4. Runs the operation async in the background
5. Emits progress signals as work progresses
6. Cleans up the object when done

### Caller Credential Handling

The daemon identifies callers via D-Bus:

```python
async def _get_caller_credentials(self, sender: str) -> tuple[int, int, int]:
    """Get UID, GID, PID of D-Bus caller."""
    # Query org.freedesktop.DBus for caller identity
    # Read /proc/{pid}/status for GID
    # Read /proc/{pid}/environ for environment
```

This allows the daemon to:
- Set up user accounts in containers with matching UID/GID
- Pass through caller's environment variables
- Mount caller's home directory

---

## Container Configuration

Kapsule applies configuration directly to each container at creation time
(rather than via a shared Incus profile) so that changes to defaults never
affect existing containers.

### Security Settings
```yaml
security.privileged: "true"   # Required for nested containers
security.nesting: "true"      # Enable Docker/Podman inside
raw.lxc: "lxc.net.0.type=none"  # Host networking
```

### Devices
- **root**: Container root filesystem
- **gpu**: GPU passthrough for graphics
- **hostfs**: Host filesystem at `/.kapsule/host` (for tooling access)

### User Setup

When entering a container, Kapsule:
1. Creates matching user account (same UID/GID)
2. Mounts home directory from host
3. Sets up environment variables (DISPLAY, XDG_*, etc.)
4. Configures shell and working directory

---

## System Integration

### D-Bus Configuration

`/usr/share/dbus-1/system.d/org.frostyard.Kapsule.conf`:
- Root owns the service name
- All users can call methods (Polkit handles authorization)

### Systemd Units

```
kapsule-daemon.service     # Main daemon (Type=dbus)
```

Plus drop-in configurations for Incus:
- Socket permissions for user access
- Log directory setup

### Configuration File

Allows distros to set default images

`/etc/kapsule.conf` or `/usr/lib/kapsule.conf`:
```ini
[kapsule]
default_container = mydev
default_image = images:archlinux
```

---

## Future Work

- **Polkit Integration** - Fine-grained authorization
- **Session Mode** - Container-local D-Bus with host forwarding
