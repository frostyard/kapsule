# Kapsule GNOME Migration Design

## Decision

Drop all KDE/Qt dependencies and reorient kapsule as a GNOME-native container management tool. Single language (Python), single package, full GNOME desktop integration.

## Architecture

```
GNOME Shell Extension (GJS)  ──┐
Nautilus Extension (Python)  ───┤
Settings App (Python/GTK4)  ────┼── D-Bus ──▶  kapsule-daemon (Python)  ──▶  Incus
CLI (Python/typer)  ────────────┤       org.frostyard.Kapsule
Ptyxis Profiles (GSettings)  ──┘
```

The Python D-Bus daemon remains the core. It is desktop-agnostic. Everything above it changes from C++/Qt/KDE to Python/GTK/GNOME.

D-Bus bus name: `org.frostyard.Kapsule`
Object path root: `/org/frostyard/Kapsule`

## What Changes, What Stays

### Stays as-is

- `src/daemon/` -- entire Python daemon (D-Bus interface, Incus client, operation tracking, container service, config handling)
- `data/dbus/`, `data/systemd/`, `data/modules-load.d/` -- system integration files (bus name updated)
- `tests/integration/` -- shell-based integration tests against the daemon

### Gets removed

- `src/cli/` -- C++ CLI
- `src/libkapsule-qt/` -- Qt/KDE library
- `CMakeLists.txt` and all CMake build infrastructure
- All Qt6, KF6, QCoro, and ECM dependencies

### Gets added

- `src/client/` -- Python D-Bus client library
- `src/cli/` -- Python CLI (typer + rich)
- `src/gnome/shell-extension/` -- GJS Shell extension
- `src/gnome/nautilus/` -- Nautilus Python extension
- `src/gnome/settings/` -- GTK4/libadwaita settings app
- `data/applications/` -- .desktop file for Settings app

## Python Client Library & CLI

The client library (`src/client/`) wraps every D-Bus method on `org.frostyard.Kapsule.Manager` into async Python calls. It handles subscribing to operation signals for progress tracking.

```python
async with KapsuleClient() as client:
    op = await client.create_container("my-dev", image="images:ubuntu/24.04")
    async for progress in op:
        print(progress.message)

    containers = await client.list_containers()
    await client.enter_container("my-dev")
```

The CLI replaces the C++ one with identical commands: `kapsule create`, `kapsule enter`, `kapsule list`, `kapsule delete`, etc. Built with `typer` for argument parsing and `rich` for colored output and progress bars. The CLI is a thin layer over the client library with no business logic.

Single package, three entry points:
- `kapsule` -- the CLI
- `kapsule-daemon` -- the daemon
- `kapsule-settings` -- the GTK settings app

## GNOME Shell Extension

Written in GJS (mandatory for GNOME Shell extensions). Connects to the daemon over D-Bus using Gio.

Features:
- List of containers with status (running/stopped) in a top-bar dropdown
- One-click to enter a running container (opens Ptyxis with that container's profile)
- Start/stop toggle per container
- "Create Container" action that opens the Settings app

Subscribes to D-Bus signals for live updates. No polling.

Installed to `~/.local/share/gnome-shell/extensions/kapsule@frostyard.org/`. Standard structure: `extension.js`, `metadata.json`, `stylesheet.css`.

Intentionally thin -- a launcher and status display, not a management UI.

## Ptyxis Integration

When a container is created, the daemon auto-creates a matching Ptyxis profile. When deleted, the profile is cleaned up. Managed via GSettings (`org.gnome.Ptyxis`) using `gi.repository.Gio`.

Each profile gets:
- A label matching the container name
- A command set to `kapsule enter <name>`
- Optionally a distinct palette/color for visual distinction from host terminals

The Shell extension and Settings app launch Ptyxis with `ptyxis --tab-with-profile=PROFILE_UUID`.

Kapsule does not use Ptyxis's native container support (which targets Podman/toolbox). Kapsule manages Incus containers itself and uses Ptyxis purely as the terminal via the profile's custom command.

If Ptyxis is not installed, profile creation is skipped. The CLI works in any terminal. Ptyxis integration is a convenience layer, not a requirement.

## Nautilus Extension

Python extension using `nautilus-python` API (`gi.repository.Nautilus`). Installed to `~/.local/share/nautilus-python/extensions/`.

**Right-click context menu:** "Open Terminal in Container" submenu listing running containers. Selecting one opens Ptyxis with that container's profile.

The extension talks to the daemon over D-Bus. It caches the container list and refreshes on D-Bus signals.

Kept minimal -- no file operations, no browsing container-internal paths. The home directory is already shared. This is a shortcut to open a terminal in the right context.

## Settings App

Standalone GTK4/libadwaita app. Not a GNOME Settings panel plugin (the API is too restrictive). Standard approach consistent with Boxes, Pods, etc.

Built with PyGObject. Launches via `.desktop` file or from the Shell extension.

**Main view:** List of containers showing name, image, status. Each row has start/stop/enter/delete actions. "Add Container" button at the top.

**Create dialog:** Pick an image from a searchable list (fetched from Incus image server), set a name, create. Simple -- advanced options come later.

**Container detail view:** Full info (image, created date, status, IP, devices). Start/stop/enter/delete. Live operation log with progress via daemon signals.

All communication over D-Bus. Subscribes to signals for live updates -- no polling.

## Build & Packaging

CMake goes away. Pure Python project built with `pyproject.toml`.

```
kapsule/
├── pyproject.toml
├── src/
│   ├── daemon/
│   ├── client/
│   ├── cli/
│   └── gnome/
│       ├── settings/
│       └── nautilus/
├── src/gnome/shell-extension/
├── data/
│   ├── dbus/
│   ├── systemd/
│   ├── modules-load.d/
│   └── applications/
├── tests/
│   └── integration/
└── scripts/
```

Python dependencies added: `PyGObject` for GTK4/libadwaita/Gio. Everything else (`dbus-fast`, `typer`, `rich`, `httpx`, `pydantic`) already exists.

Runtime dependencies: `gtk4`, `libadwaita`, `nautilus-python`, `ptyxis` -- all optional. The daemon and CLI work without any of them.

Shell extension and Nautilus extension install via an install script (files copied to well-known paths).

## Testing & Error Handling

### Testing

- **Existing integration tests** stay -- they test daemon and container lifecycle over D-Bus
- **Client library** gets unit tests with mocked D-Bus connections
- **CLI** tested via typer's `CliRunner` with client library mocked
- **Settings app and Nautilus extension** -- manual testing backed by the integration test suite
- **Shell extension** -- manual testing (standard practice for GNOME Shell extensions)

### Error handling

- Client library translates D-Bus errors into Python exceptions with clear messages
- CLI catches exceptions, prints with rich formatting (red text, context)
- Settings app shows errors as libadwaita toast notifications (non-blocking, auto-dismissing)
- Daemon not running: client raises `DaemonNotRunning`, CLI tells you the systemctl command, Settings app offers a button to start it
