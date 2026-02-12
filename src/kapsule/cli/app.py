"""Kapsule CLI application."""

from __future__ import annotations

import asyncio
import functools
import os

import typer

from kapsule.cli.output import console, print_containers, print_error, print_success
from kapsule.client import DaemonNotRunning, KapsuleClient

app = typer.Typer(
    name="kapsule",
    help="Manage Incus containers with GNOME integration.",
    no_args_is_help=True,
)


def run_async(coro):
    """Run an async coroutine from sync typer commands."""
    return asyncio.run(coro)


def handle_errors(func):
    """Decorator to catch common client errors."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DaemonNotRunning as e:
            print_error(str(e))
            raise typer.Exit(1) from None
        except Exception as e:
            print_error(str(e))
            raise typer.Exit(1) from None
    return wrapper


@app.command()
@handle_errors
def create(
    name: str = typer.Argument(..., help="Container name"),
    image: str = typer.Option("", "--image", "-i", help="Image to use"),
    session_mode: bool = typer.Option(
        False, "--session", help="Enable session mode"
    ),
    dbus_mux: bool = typer.Option(
        False, "--dbus-mux", help="Enable D-Bus multiplexing"
    ),
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


@app.command("ls", hidden=True)
@handle_errors
def list_containers_alias(
    all_: bool = typer.Option(False, "--all", "-a", help="Show stopped containers too"),
):
    """List containers (alias)."""
    list_containers(all_=all_)


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


@app.command("remove", hidden=True)
@handle_errors
def remove_alias(
    name: str = typer.Argument(..., help="Container name"),
    force: bool = typer.Option(False, "--force", "-f", help="Force removal"),
):
    """Remove a container (alias)."""
    rm(name=name, force=force)


@app.command()
@handle_errors
def config(
    key: str | None = typer.Argument(None, help="Config key to show"),
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
