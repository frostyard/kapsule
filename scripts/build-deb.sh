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

# Relocate venv to target path (/usr/bin/python3) so it works on the installed
# system rather than pointing at the build machine's Python.
VENV_BIN="$STAGING/usr/lib/kapsule/venv/bin"
TARGET_PYTHON="/usr/bin/python3"
ln -sf "$TARGET_PYTHON" "$VENV_BIN/python3"
ln -sf python3 "$VENV_BIN/python"
# Rewrite shebangs in venv scripts from the build-time Python to the target path.
for f in "$VENV_BIN"/*; do
    [ -f "$f" ] && head -1 "$f" | grep -q "^#!.*python" && \
        sed -i "1s|#!.*|#!$TARGET_PYTHON|" "$f"
done
# Patch pyvenv.cfg so Python resolves the base interpreter on the target system.
sed -i \
    -e "s|^home = .*|home = /usr/bin|" \
    -e "s|^executable = .*|executable = $TARGET_PYTHON|" \
    -e "/^command = /d" \
    "$STAGING/usr/lib/kapsule/venv/pyvenv.cfg"

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
