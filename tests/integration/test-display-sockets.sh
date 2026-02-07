#!/bin/bash

# SPDX-FileCopyrightText: 2026 Lasath Fernando <devel@lasath.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# Test: Display socket passthrough (X11 and Wayland)
#
# Tests that X11 and Wayland sockets are correctly mounted/symlinked
# in containers and that graphical applications can connect to the
# host's display server.

source "$(dirname "${BASH_SOURCE[0]}")/helpers.sh"

CONTAINER_NAME="test-display-sockets"

# Helper to run commands in container via kapsule enter
# Exports DISPLAY, WAYLAND_DISPLAY, and XAUTHORITY so the daemon (which reads
# /proc/<pid>/environ) sets up the correct symlinks.
kapsule_exec() {
    ssh_vm "DISPLAY=$HOST_DISPLAY WAYLAND_DISPLAY=$HOST_WAYLAND XAUTHORITY=$HOST_XAUTHORITY kapsule enter '$CONTAINER_NAME' -- $*"
}

# ============================================================================
# Setup
# ============================================================================

cleanup_container "$CONTAINER_NAME"

# Display env vars are not set over SSH, so use the known defaults
# for a typical KDE Plasma session on the VM
HOST_DISPLAY=":0"
HOST_WAYLAND="wayland-0"
HOST_UID=$(ssh_vm "id -u")

# XAUTHORITY has a random filename — discover it from the running session
HOST_XAUTHORITY=$(ssh_vm "cat /proc/\$(pgrep -u \$(id -u) plasmashell | head -1)/environ 2>/dev/null | tr '\0' '\n' | grep ^XAUTHORITY= | cut -d= -f2")

echo "Host environment:"
echo "  DISPLAY=$HOST_DISPLAY"
echo "  WAYLAND_DISPLAY=$HOST_WAYLAND"
echo "  XAUTHORITY=$HOST_XAUTHORITY"
echo "  UID=$HOST_UID"

# ============================================================================
# Tests
# ============================================================================

echo ""
echo "Testing display socket passthrough..."

# Test: Create container
echo ""
echo "1. Create container"
output=$(create_container "$CONTAINER_NAME" "images:archlinux" 2>&1) || {
    echo "Create failed with output:"
    echo "$output"
    exit 1
}
assert_container_exists "$CONTAINER_NAME"
assert_container_state "$CONTAINER_NAME" "RUNNING"

# Wait for container to fully initialize
echo ""
echo "2. Waiting for container to initialize..."
sleep 3

# ============================================================================
# X11 socket tests
# ============================================================================

echo ""
echo "3. Checking X11 socket passthrough"

# The X11 socket directory is created at enter time and the individual
# socket is symlinked to the host via hostfs
if kapsule_exec "test -d /tmp/.X11-unix" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} /tmp/.X11-unix directory exists"
else
    echo -e "  ${RED}✗${NC} /tmp/.X11-unix directory missing"
    exit 1
fi

# Check that the specific X socket is a symlink to the host
display_num="${HOST_DISPLAY#:}"
display_num="${display_num%%.*}"  # strip screen number if present

if kapsule_exec "test -L /tmp/.X11-unix/X${display_num}" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} X11 socket X${display_num} is a symlink"

    target=$(kapsule_exec "readlink /tmp/.X11-unix/X${display_num}" 2>/dev/null)
    expected_target="/.kapsule/host/tmp/.X11-unix/X${display_num}"
    if [[ "$target" == "$expected_target" ]]; then
        echo -e "  ${GREEN}✓${NC} X11 symlink points to host socket"
    else
        echo -e "  ${RED}✗${NC} X11 symlink has wrong target: $target (expected $expected_target)"
        exit 1
    fi
else
    echo -e "  ${RED}✗${NC} X11 socket X${display_num} not found as symlink"
    exit 1
fi

# Check XAUTHORITY symlink
echo ""
echo "4. Checking XAUTHORITY symlink"
if [[ -n "$HOST_XAUTHORITY" ]]; then
    xauth_basename=$(basename "$HOST_XAUTHORITY")
    if kapsule_exec "test -L /run/user/$HOST_UID/$xauth_basename" 2>/dev/null; then
        target=$(kapsule_exec "readlink /run/user/$HOST_UID/$xauth_basename" 2>/dev/null)
        expected_target="/.kapsule/host/run/user/$HOST_UID/$xauth_basename"
        if [[ "$target" == "$expected_target" ]]; then
            echo -e "  ${GREEN}✓${NC} XAUTHORITY symlink points to host file"
        else
            echo -e "  ${RED}✗${NC} XAUTHORITY symlink has wrong target: $target (expected $expected_target)"
            exit 1
        fi
    else
        echo -e "  ${RED}✗${NC} XAUTHORITY symlink not found for $xauth_basename"
        exit 1
    fi
else
    echo -e "  ${YELLOW}!${NC} XAUTHORITY not discovered from host session, skipping"
fi

# ============================================================================
# Wayland socket tests
# ============================================================================

echo ""
echo "5. Checking Wayland socket passthrough"

if [[ -n "$HOST_WAYLAND" ]]; then
    if kapsule_exec "test -L /run/user/$HOST_UID/$HOST_WAYLAND" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Wayland socket symlink exists"

        target=$(kapsule_exec "readlink /run/user/$HOST_UID/$HOST_WAYLAND" 2>/dev/null)
        expected_target="/.kapsule/host/run/user/$HOST_UID/$HOST_WAYLAND"
        if [[ "$target" == "$expected_target" ]]; then
            echo -e "  ${GREEN}✓${NC} Wayland symlink points to host socket"
        else
            echo -e "  ${RED}✗${NC} Wayland symlink has wrong target: $target (expected $expected_target)"
            exit 1
        fi
    else
        echo -e "  ${RED}✗${NC} Wayland socket symlink not created for $HOST_WAYLAND"
        exit 1
    fi
else
    echo -e "  ${YELLOW}!${NC} WAYLAND_DISPLAY not set on host, skipping Wayland socket check"
fi

# Check host socket accessible through hostfs
echo ""
echo "6. Checking host socket accessibility through hostfs"

if [[ -n "$HOST_WAYLAND" ]]; then
    if kapsule_exec "test -e /.kapsule/host/run/user/$HOST_UID/$HOST_WAYLAND" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} Host Wayland socket accessible via hostfs"
    else
        echo -e "  ${RED}✗${NC} Host Wayland socket not accessible via hostfs"
        exit 1
    fi
fi

if kapsule_exec "test -d /.kapsule/host/tmp/.X11-unix" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Host X11 socket directory accessible via hostfs"
else
    echo -e "  ${YELLOW}!${NC} Host X11 socket directory not accessible via hostfs"
fi

# ============================================================================
# Install display tools
# ============================================================================

echo ""
echo "7. Installing display tools..."
# xorg-xdpyinfo: validates X11 connection (tiny, libX11 only)
# xorg-xmessage: lightest X11 app with a real window + built-in timeout
# wayland-utils: wayland-info validates Wayland connection (libwayland-client only)
# foot: lightest Wayland-native terminal, can run a command and exit
# ttf-dejavu: monospace font required by foot
# mesa-utils: glxinfo/eglinfo for GPU validation
kapsule_exec "sudo pacman -Syu --noconfirm xorg-xdpyinfo xorg-xmessage wayland-utils foot ttf-dejavu mesa-utils" &>/dev/null || {
    echo -e "  ${YELLOW}!${NC} Failed to install some display packages"
}

# ============================================================================
# X11 connection tests
# ============================================================================

echo ""
echo "8. Testing X11 connection with xdpyinfo"
if [[ -n "$HOST_DISPLAY" ]]; then
    xdpyinfo_output=$(kapsule_exec "xdpyinfo" 2>&1)
    xdpyinfo_exit=$?
    if [[ $xdpyinfo_exit -eq 0 ]]; then
        echo -e "  ${GREEN}✓${NC} xdpyinfo succeeded"
        screen_line=$(echo "$xdpyinfo_output" | grep "dimensions:" | head -1)
        if [[ -n "$screen_line" ]]; then
            echo "    $screen_line"
        fi
    else
        echo -e "  ${RED}✗${NC} xdpyinfo failed"
        echo "    $xdpyinfo_output"
        exit 1
    fi
else
    echo -e "  ${YELLOW}!${NC} Skipping X11 connection test (DISPLAY not set)"
fi

echo ""
echo "9. Testing X11 window creation with xmessage"
if [[ -n "$HOST_DISPLAY" ]]; then
    # xmessage -timeout N exits after N seconds with code 0
    xmessage_output=$(kapsule_exec "xmessage -timeout 3 'Kapsule X11 test'" 2>&1)
    xmessage_exit=$?
    if [[ $xmessage_exit -eq 0 ]]; then
        echo -e "  ${GREEN}✓${NC} xmessage window created and exited cleanly"
    else
        echo -e "  ${RED}✗${NC} xmessage failed (exit $xmessage_exit)"
        echo "    $xmessage_output"
        exit 1
    fi
else
    echo -e "  ${YELLOW}!${NC} Skipping X11 window test (DISPLAY not set)"
fi

echo ""
echo "10. Testing GPU (X11) with glxinfo"
if [[ -n "$HOST_DISPLAY" ]]; then
    glxinfo_output=$(kapsule_exec "glxinfo -B" 2>&1)
    glxinfo_exit=$?
    if [[ $glxinfo_exit -eq 0 ]]; then
        echo -e "  ${GREEN}✓${NC} glxinfo succeeded"
        renderer=$(echo "$glxinfo_output" | grep "OpenGL renderer" | head -1)
        if [[ -n "$renderer" ]]; then
            echo "    $renderer"
        fi
    else
        echo -e "  ${RED}✗${NC} glxinfo failed"
        echo "    $glxinfo_output"
        exit 1
    fi
else
    echo -e "  ${YELLOW}!${NC} Skipping glxinfo test (DISPLAY not set)"
fi

# ============================================================================
# Wayland connection tests
# ============================================================================

echo ""
echo "11. Testing Wayland connection with wayland-info"
if [[ -n "$HOST_WAYLAND" ]]; then
    wayinfo_output=$(kapsule_exec "wayland-info" 2>&1)
    wayinfo_exit=$?
    if [[ $wayinfo_exit -eq 0 ]]; then
        echo -e "  ${GREEN}✓${NC} wayland-info succeeded"
        compositor=$(echo "$wayinfo_output" | grep -i "compositor" | head -1)
        if [[ -n "$compositor" ]]; then
            echo "    $compositor"
        fi
    else
        echo -e "  ${RED}✗${NC} wayland-info failed"
        echo "    $wayinfo_output"
        exit 1
    fi
else
    echo -e "  ${YELLOW}!${NC} Skipping Wayland connection test (WAYLAND_DISPLAY not set)"
fi

echo ""
echo "12. Testing Wayland window creation with foot"
if [[ -n "$HOST_WAYLAND" ]]; then
    # foot -e <cmd> opens a terminal, runs the command, and exits
    foot_output=$(kapsule_exec "foot -e true" 2>&1)
    foot_exit=$?
    if [[ $foot_exit -eq 0 ]]; then
        echo -e "  ${GREEN}✓${NC} foot window created and exited cleanly"
    else
        echo -e "  ${RED}✗${NC} foot failed (exit $foot_exit)"
        echo "    $foot_output"
        exit 1
    fi
else
    echo -e "  ${YELLOW}!${NC} Skipping Wayland window test (WAYLAND_DISPLAY not set)"
fi

echo ""
echo "13. Testing GPU (Wayland) with eglinfo"
if [[ -n "$HOST_WAYLAND" ]]; then
    # eglinfo often exits non-zero when some platforms (GBM, device) fail,
    # even if Wayland/X11 platforms work fine. Use || true to prevent set -e.
    eglinfo_output=$(kapsule_exec "eglinfo" 2>&1) || true
    if echo "$eglinfo_output" | grep -qi "renderer"; then
        echo -e "  ${GREEN}✓${NC} eglinfo found a renderer"
        renderer=$(echo "$eglinfo_output" | grep -i "renderer" | head -1)
        echo "    $renderer"
    else
        echo -e "  ${YELLOW}!${NC} eglinfo could not find a renderer"
    fi
else
    echo -e "  ${YELLOW}!${NC} Skipping eglinfo test (WAYLAND_DISPLAY not set)"
fi

# ============================================================================
# Cleanup
# ============================================================================

echo ""
echo "14. Cleanup"
cleanup_container "$CONTAINER_NAME"
assert_container_not_exists "$CONTAINER_NAME"

echo ""
echo "Display socket passthrough tests passed!"
