# .deb Packaging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a .deb package via GitHub Actions using nfpm, triggered on v* git tags.

**Architecture:** A build script (`scripts/build-deb.sh`) stages all files into `build/staging/` with their target filesystem layout — vendored Python venv, wrapper scripts, resolved systemd unit, and system files. nfpm then maps the staging tree into a .deb. A GitHub Actions workflow orchestrates the whole thing on tag push.

**Tech Stack:** nfpm, bash, GitHub Actions, Python venv

**Design doc:** `docs/plans/2026-02-11-deb-packaging-design.md`

---

### Task 1: Create the build script

**Files:**
- Create: `scripts/build-deb.sh`

**Step 1: Write the build script**

```bash
#!/bin/bash
# Build staging directory for .deb packaging via nfpm.
# Run from repo root. Produces build/staging/ with target filesystem layout.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
STAGING="$PROJECT_DIR/build/staging"

echo "==> Cleaning staging directory"
rm -rf "$STAGING"

# --- Vendored venv ---
echo "==> Creating vendored venv"
python3 -m venv --system-site-packages "$STAGING/usr/lib/kapsule/venv"
"$STAGING/usr/lib/kapsule/venv/bin/pip" install --no-cache-dir "$PROJECT_DIR"

# --- Wrapper scripts ---
echo "==> Generating wrapper scripts"
mkdir -p "$STAGING/usr/bin"

cat > "$STAGING/usr/bin/kapsule" << 'WRAPPER'
#!/bin/sh
exec /usr/lib/kapsule/venv/bin/python -m kapsule.cli "$@"
WRAPPER
chmod 755 "$STAGING/usr/bin/kapsule"

cat > "$STAGING/usr/bin/kapsule-daemon" << 'WRAPPER'
#!/bin/sh
exec /usr/lib/kapsule/venv/bin/python -m kapsule.daemon "$@"
WRAPPER
chmod 755 "$STAGING/usr/bin/kapsule-daemon"

cat > "$STAGING/usr/bin/kapsule-settings" << 'WRAPPER'
#!/bin/sh
exec /usr/lib/kapsule/venv/bin/python -m kapsule.gnome.settings.app "$@"
WRAPPER
chmod 755 "$STAGING/usr/bin/kapsule-settings"

# --- Systemd unit (resolve placeholders) ---
echo "==> Resolving systemd unit placeholders"
mkdir -p "$STAGING/usr/lib/systemd/system"
sed \
    -e 's|@PYTHON_EXECUTABLE@|/usr/lib/kapsule/venv/bin/python|g' \
    -e '/^Environment=PYTHONPATH=/d' \
    "$PROJECT_DIR/data/systemd/system/kapsule-daemon.service" \
    > "$STAGING/usr/lib/systemd/system/kapsule-daemon.service"

echo "==> Staging complete"
```

**Step 2: Make it executable**

Run: `chmod +x scripts/build-deb.sh`

**Step 3: Commit**

```bash
git add scripts/build-deb.sh
git commit -m "feat: add build-deb.sh staging script for .deb packaging"
```

---

### Task 2: Create postinstall and postremove scripts

**Files:**
- Create: `scripts/postinstall.sh`
- Create: `scripts/postremove.sh`

**Step 1: Write postinstall.sh**

```bash
#!/bin/sh
systemctl daemon-reload
```

**Step 2: Write postremove.sh**

```bash
#!/bin/sh
systemctl daemon-reload
```

**Step 3: Make them executable**

Run: `chmod +x scripts/postinstall.sh scripts/postremove.sh`

**Step 4: Commit**

```bash
git add scripts/postinstall.sh scripts/postremove.sh
git commit -m "feat: add postinstall/postremove scripts for systemd daemon-reload"
```

---

### Task 3: Create nfpm.yaml

**Files:**
- Create: `nfpm.yaml` (repo root)

**Step 1: Write nfpm.yaml**

The venv is staged by `build-deb.sh` into `build/staging/`. nfpm maps it plus static repo files to their target paths. The version uses `${VERSION}` env var (semver parser strips any `v` prefix automatically). Config files use `type: config` so they're preserved on upgrade.

```yaml
name: kapsule
arch: amd64
platform: linux
version: ${VERSION}
version_schema: semver
maintainer: Frostyard
description: Incus-based container management with GNOME integration
vendor: Frostyard
homepage: https://github.com/frostyard/kapsule
license: GPL-3.0-or-later

depends:
  - python3 (>= 3.11)
  - python3-gi
  - gir1.2-adw-1
  - gir1.2-gtk-4.0

recommends:
  - incus
  - ptyxis

scripts:
  postinstall: scripts/postinstall.sh
  postremove: scripts/postremove.sh

contents:
  # Vendored Python venv
  - src: build/staging/usr/lib/kapsule/
    dst: /usr/lib/kapsule/
    type: tree

  # Wrapper scripts
  - src: build/staging/usr/bin/kapsule
    dst: /usr/bin/kapsule
    file_info:
      mode: 0755
  - src: build/staging/usr/bin/kapsule-daemon
    dst: /usr/bin/kapsule-daemon
    file_info:
      mode: 0755
  - src: build/staging/usr/bin/kapsule-settings
    dst: /usr/bin/kapsule-settings
    file_info:
      mode: 0755
  - src: kapsule
    dst: /usr/bin/kap
    type: symlink

  # D-Bus
  - src: data/dbus/system/org.frostyard.Kapsule.conf
    dst: /etc/dbus-1/system.d/org.frostyard.Kapsule.conf
    type: config
  - src: data/dbus/system/org.frostyard.Kapsule.service
    dst: /usr/share/dbus-1/system-services/org.frostyard.Kapsule.service

  # Systemd (resolved unit from staging, static files from repo)
  - src: build/staging/usr/lib/systemd/system/kapsule-daemon.service
    dst: /usr/lib/systemd/system/kapsule-daemon.service
  - src: data/systemd/system-preset/50-kapsule.preset
    dst: /usr/lib/systemd/system-preset/50-kapsule.preset
  - src: data/systemd/system/incus.service.d/kapsule-log-dir.conf
    dst: /usr/lib/systemd/system/incus.service.d/kapsule-log-dir.conf
  - src: data/systemd/system/incus.socket.d/kapsule-socket-group.conf
    dst: /usr/lib/systemd/system/incus.socket.d/kapsule-socket-group.conf
  - src: data/systemd/system/incus-user.socket.d/kapsule-socket-mode.conf
    dst: /usr/lib/systemd/system/incus-user.socket.d/kapsule-socket-mode.conf

  # Modules
  - src: data/modules-load.d/kapsule.conf
    dst: /usr/lib/modules-load.d/kapsule.conf

  # Config
  - src: data/kapsule.conf
    dst: /etc/kapsule.conf
    type: config

  # GNOME Shell extension
  - src: src/gnome/shell-extension/extension.js
    dst: /usr/share/gnome-shell/extensions/kapsule@frostyard.org/extension.js
  - src: src/gnome/shell-extension/metadata.json
    dst: /usr/share/gnome-shell/extensions/kapsule@frostyard.org/metadata.json
  - src: src/gnome/shell-extension/stylesheet.css
    dst: /usr/share/gnome-shell/extensions/kapsule@frostyard.org/stylesheet.css

  # Nautilus extension
  - src: src/gnome/nautilus/kapsule-nautilus.py
    dst: /usr/share/nautilus-python/extensions/kapsule-nautilus.py

  # Desktop file
  - src: data/applications/org.frostyard.Kapsule.desktop
    dst: /usr/share/applications/org.frostyard.Kapsule.desktop
```

**Step 2: Commit**

```bash
git add nfpm.yaml
git commit -m "feat: add nfpm.yaml for .deb package configuration"
```

---

### Task 4: Create GitHub Actions workflow

**Files:**
- Create: `.github/workflows/build-deb.yml`

**Step 1: Write the workflow**

```yaml
name: Build .deb Package

on:
  push:
    tags:
      - "v*"

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install nfpm
        run: |
          echo 'deb [trusted=yes] https://repo.goreleaser.com/apt/ /' | sudo tee /etc/apt/sources.list.d/goreleaser.list
          sudo apt-get update
          sudo apt-get install -y nfpm

      - name: Build staging
        run: scripts/build-deb.sh

      - name: Build .deb
        run: nfpm package --packager deb --target build/
        env:
          VERSION: ${{ github.ref_name }}

      - uses: actions/upload-artifact@v4
        with:
          name: kapsule-deb
          path: build/*.deb
```

Note: `VERSION` is set to the full tag (e.g. `v0.1.0`). nfpm's `version_schema: semver` parser strips the `v` prefix automatically.

**Step 2: Commit**

```bash
git add .github/workflows/build-deb.yml
git commit -m "feat: add GitHub Actions workflow to build .deb on tag push"
```

---

### Task 5: Add build/ to .gitignore

**Files:**
- Modify: `.gitignore`

**Step 1: Append build/ to .gitignore**

Add this line (if not already present):

```
build/
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add build/ to .gitignore"
```

---

### Task 6: Local verification

**Step 1: Run the build script**

Run: `scripts/build-deb.sh`

Expected: Completes without errors, prints staging progress.

**Step 2: Verify staged systemd unit**

Run: `cat build/staging/usr/lib/systemd/system/kapsule-daemon.service`

Expected:
- `ExecStart=/usr/lib/kapsule/venv/bin/python -m kapsule.daemon --system`
- No `@PYTHON_EXECUTABLE@` placeholder
- No `Environment=PYTHONPATH=` line

**Step 3: Verify wrapper scripts exist and are executable**

Run: `ls -la build/staging/usr/bin/`

Expected: `kapsule`, `kapsule-daemon`, `kapsule-settings` all with 755 permissions.

**Step 4: Verify the venv works**

Run: `build/staging/usr/lib/kapsule/venv/bin/python -c "import kapsule; print('ok')"`

Expected: Prints `ok`.

**Step 5: Verify nfpm can package (requires nfpm installed locally)**

Run: `VERSION=0.1.0 nfpm package --packager deb --target build/`

Expected: Produces `build/kapsule_0.1.0_amd64.deb`.

If nfpm is not installed locally, skip this step — CI will verify it.
