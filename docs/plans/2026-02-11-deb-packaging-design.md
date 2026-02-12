# Kapsule .deb Packaging Design

## Overview

Build a `.deb` package via GitHub Actions using nfpm, triggered on `v*` tags. The package bundles a vendored Python virtualenv at `/usr/lib/kapsule/venv/` with all Python dependencies, plus system integration files (D-Bus, systemd, GNOME extensions). amd64 only.

The user handles uploading the built `.deb` to their own Debian repository via a separate GitHub Action.

## GitHub Action Workflow

**Trigger:** Push of tags matching `v*` (e.g. `v0.1.0`).

**Single job** on `ubuntu-latest`, amd64:

1. Checkout the repo
2. Set up Python 3.11
3. Install nfpm
4. Run `scripts/build-deb.sh` which stages all files
5. Run `nfpm package --packager deb`
6. Upload the `.deb` as a workflow artifact

**Version:** Extracted from the git tag by stripping the `v` prefix. Passed to nfpm via `NFPM_VERSION` environment variable.

## File Layout Inside the .deb

```
/usr/lib/kapsule/venv/                              # Vendored Python venv
/usr/bin/kapsule                                     # Wrapper script
/usr/bin/kap                                         # Symlink -> kapsule
/usr/bin/kapsule-daemon                              # Wrapper script
/usr/bin/kapsule-settings                            # Wrapper script
/etc/dbus-1/system.d/org.frostyard.Kapsule.conf
/usr/share/dbus-1/system-services/org.frostyard.Kapsule.service
/usr/lib/systemd/system/kapsule-daemon.service
/usr/lib/systemd/system-preset/50-kapsule.preset
/usr/lib/systemd/system/incus.service.d/kapsule-log-dir.conf
/usr/lib/systemd/system/incus.socket.d/kapsule-socket-group.conf
/usr/lib/systemd/system/incus-user.socket.d/kapsule-socket-mode.conf
/usr/lib/modules-load.d/kapsule.conf
/etc/kapsule.conf
/usr/share/gnome-shell/extensions/kapsule@frostyard.org/extension.js
/usr/share/gnome-shell/extensions/kapsule@frostyard.org/metadata.json
/usr/share/gnome-shell/extensions/kapsule@frostyard.org/stylesheet.css
/usr/share/nautilus-python/extensions/kapsule-nautilus.py
/usr/share/applications/org.frostyard.Kapsule.desktop
```

## Vendored Virtualenv

Created with `python3 -m venv --system-site-packages /path/to/staging/usr/lib/kapsule/venv/`.

`--system-site-packages` is required so the venv can access system-installed `python3-gi` (PyGObject) and GObject Introspection typelibs. These cannot be pip-installed and must come from system packages.

The project itself is pip-installed into the venv (`pip install .`), which pulls in all dependencies from `pyproject.toml`: httpx, dbus-fast (with Cython), typer, rich, pyyaml, pydantic.

## Wrapper Scripts

Thin shell scripts in `/usr/bin/` that exec into the venv's Python:

```sh
#!/bin/sh
exec /usr/lib/kapsule/venv/bin/python -m kapsule.cli "$@"
```

- `/usr/bin/kapsule` -- `python -m kapsule.cli`
- `/usr/bin/kap` -- symlink to `kapsule`
- `/usr/bin/kapsule-daemon` -- `python -m kapsule.daemon`
- `/usr/bin/kapsule-settings` -- `python -m kapsule.gnome.settings.app`

## Systemd Unit Substitution

The source `data/systemd/system/kapsule-daemon.service` contains placeholders:

- `@PYTHON_EXECUTABLE@` -> `/usr/lib/kapsule/venv/bin/python`
- `@KAPSULE_VENDOR_DIR@` and `@KAPSULE_PYTHON_DIR@` -> removed (venv handles paths)

The `PYTHONPATH` environment line is dropped entirely since the venv already has everything on its path. The resolved `ExecStart` becomes:

```
ExecStart=/usr/lib/kapsule/venv/bin/python -m kapsule.daemon --system
```

## Build Script (scripts/build-deb.sh)

Orchestrates the staging before nfpm runs:

1. Clean and create `build/staging/`
2. Create the venv at `build/staging/usr/lib/kapsule/venv/`
3. Pip install the project into the venv
4. Generate wrapper scripts into `build/staging/usr/bin/`
5. Substitute placeholders in systemd unit, write resolved copy to staging
6. Copy system files to their target paths under staging:
   - D-Bus configs -> `build/staging/etc/dbus-1/system.d/` and `build/staging/usr/share/dbus-1/system-services/`
   - Systemd units + drop-ins -> `build/staging/usr/lib/systemd/system/`
   - Systemd preset -> `build/staging/usr/lib/systemd/system-preset/`
   - Modules-load.d -> `build/staging/usr/lib/modules-load.d/`
   - Config -> `build/staging/etc/`
   - GNOME Shell extension -> `build/staging/usr/share/gnome-shell/extensions/kapsule@frostyard.org/`
   - Nautilus extension -> `build/staging/usr/share/nautilus-python/extensions/`
   - Desktop file -> `build/staging/usr/share/applications/`
7. Done -- nfpm is invoked by the GitHub Action, not by this script

## nfpm Configuration (nfpm.yaml)

At the repo root. Key fields:

- **name:** `kapsule`
- **version:** `${NFPM_VERSION}` (from environment, set by CI from git tag)
- **arch:** `amd64`
- **maintainer:** Frostyard
- **description:** Incus-based container management with GNOME integration
- **license:** GPL-3.0-or-later
- **depends:** `python3 (>= 3.11)`, `python3-gi`, `gir1.2-adw-1`, `gir1.2-gtk-4.0`
- **recommends:** `incus`, `ptyxis`
- **contents:** `src`/`dst` pairs mapping `build/staging/...` to `/...`

## Debian Dependencies

### Required (depends)

- `python3 (>= 3.11)` -- runtime interpreter
- `python3-gi` -- PyGObject for GTK4/libadwaita (settings app, nautilus extension)
- `gir1.2-adw-1` -- libadwaita typelib
- `gir1.2-gtk-4.0` -- GTK4 typelib

### Recommended (recommends)

- `incus` -- the container backend (core functionality needs it, but the package should install cleanly without it)
- `ptyxis` -- terminal integration (optional convenience)

## Post-Install / Post-Remove

nfpm supports scriptlets. The package includes:

- **postinstall:** `systemctl daemon-reload` to pick up the new unit files
- **postremove:** `systemctl daemon-reload` to clean up
