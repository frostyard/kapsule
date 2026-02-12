<!--
SPDX-FileCopyrightText: 2026 Frostyard

SPDX-License-Identifier: CC-BY-SA-4.0
-->

# Kapsule

Incus-based container management with native GNOME integration.

A distrobox-like tool using Incus as the container/VM backend, with deep GNOME desktop integration.

## Features

- **Nested containerization** - Create containers that can run Docker/Podman inside them
- **Host integration** - Containers share your home directory, user account, environment, Wayland/PipeWire sockets, and D-Bus session
- **GNOME integration** - Shell extension, Nautilus context menu, Ptyxis terminal profiles, GTK4 settings app

## Quick Start

```bash
# Create and enter your distro's default container
kapsule enter

# Create and enter a container
kapsule create my-dev --image images:ubuntu/24.04
kapsule enter my-dev

# Inside the container, you have access to:
# - Your home directory (mounted at /home/<username>)
# - Your user account (same UID/GID)
# - Your environment variables
# - Docker/Podman capability
```

## Installation

```bash
# Install with pip (editable mode)
pip install -e .

# Install GNOME extensions (Shell, Nautilus, desktop file)
./scripts/install-gnome-extensions.sh
```

## Commands

| Command | Description |
|---------|-------------|
| `kapsule create <name>` | Create a new container |
| `kapsule enter <name>` | Enter a container (interactive shell) |
| `kapsule enter <name> -- <cmd>` | Run a command in a container |
| `kapsule list` | List running containers |
| `kapsule list --all` | List all containers |
| `kapsule start <name>` | Start a stopped container |
| `kapsule stop <name>` | Stop a running container |
| `kapsule rm <name>` | Remove a container |

Use the short alias `kap` instead of `kapsule` for convenience:

```bash
kap create my-dev
kap enter my-dev
```

## Container Images

Kapsule uses Linux Containers images by default. Specify images with the `--image` flag:

```bash
# Ubuntu (default)
kapsule create dev --image images:ubuntu/24.04

# Fedora
kapsule create fedora-dev --image images:fedora/41

# Arch Linux
kapsule create arch-dev --image images:archlinux
```

See available images at: https://images.linuxcontainers.org

## How It Works

Kapsule creates Incus containers with settings that enable:

1. **Security nesting** - Allows running Docker/Podman inside the container
2. **Host networking** - Container shares the host's network namespace
3. **Device access** - GPU, audio, and display devices are available
4. **Home mount** - Your home directory is bind-mounted into the container

On first `enter`, Kapsule automatically:
- Creates your user account in the container (matching host UID/GID)
- Mounts your home directory
- Sets up XDG_RUNTIME_DIR symlink for Wayland/PipeWire

## Architecture

Kapsule is a pure Python project:

- **kapsule CLI** (Python/typer) - User-facing command-line tool
- **kapsule.client** (Python) - Async D-Bus client library
- **kapsule-daemon** (Python) - System service bridging D-Bus and Incus REST API
- **GNOME Shell extension** (GJS) - Top bar container indicator
- **Nautilus extension** (Python) - Right-click menu integration
- **Settings app** (GTK4/libadwaita) - Container management GUI

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed technical documentation.

## Requirements

- Python >= 3.11
- Incus
- systemd
- GNOME 45+ (for Shell extension)

## License

GPL-3.0-or-later
