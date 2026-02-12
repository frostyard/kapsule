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
