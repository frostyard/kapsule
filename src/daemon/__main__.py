"""Entry point for running the daemon directly.

Usage:
    python -m kapsule.daemon
    python -m kapsule.daemon --system  # Use system bus (requires root/polkit)
    python -m kapsule.daemon proxy --container-bus unix:path=/path/to/bus
"""

from __future__ import annotations

import asyncio
import argparse
import signal
import sys


async def run_daemon(bus_type: str = "session") -> None:
    """Run the Kapsule D-Bus daemon."""
    from .service import KapsuleService

    service = KapsuleService(bus_type=bus_type)

    # Handle shutdown signals
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def handle_signal() -> None:
        print("\nShutting down...")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    try:
        await service.start()

        # Wait for either disconnect or shutdown signal
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(service.run()),
                asyncio.create_task(shutdown_event.wait()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()

    finally:
        await service.stop()


async def run_proxy(
    container_bus: str,
    host_bus: str | None = None,
) -> None:
    """Run a standalone D-Bus proxy (without the management daemon)."""
    from .dbus_proxy import DBusProxy

    proxy = DBusProxy(
        container_bus_address=container_bus,
        host_bus_address=host_bus,
    )

    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()

    def handle_signal() -> None:
        print("\nShutting down proxy...")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    try:
        await proxy.start()

        done, pending = await asyncio.wait(
            [
                asyncio.create_task(proxy.run()),
                asyncio.create_task(shutdown_event.wait()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

    finally:
        await proxy.stop()


def run() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Kapsule D-Bus daemon and proxy",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Default daemon mode (no subcommand needed for backwards compat)
    parser.add_argument(
        "--system",
        action="store_true",
        help="Use system bus instead of session bus",
    )

    # Proxy subcommand
    proxy_parser = subparsers.add_parser(
        "proxy",
        help="Run standalone D-Bus proxy for a container",
    )
    proxy_parser.add_argument(
        "--container-bus",
        required=True,
        help="D-Bus address for container session bus (e.g., unix:path=/path/to/bus)",
    )
    proxy_parser.add_argument(
        "--host-bus",
        help="D-Bus address for host session bus (defaults to DBUS_SESSION_BUS_ADDRESS)",
    )

    args = parser.parse_args()

    try:
        if args.command == "proxy":
            asyncio.run(run_proxy(args.container_bus, args.host_bus))
        else:
            # Default: run the daemon
            bus_type = "system" if args.system else "session"
            asyncio.run(run_daemon(bus_type))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
