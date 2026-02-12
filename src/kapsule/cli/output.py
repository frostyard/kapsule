"""CLI output formatting using rich."""

from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)


STATUS_COLORS = {
    "Running": "green",
    "Stopped": "red",
    "Starting": "yellow",
    "Stopping": "yellow",
}


def print_error(message: str) -> None:
    err_console.print(f"[red]error:[/red] {message}")


def print_success(message: str) -> None:
    console.print(f"[green]{message}[/green]")


def print_containers(containers: list[dict], show_all: bool = False) -> None:
    if not show_all:
        containers = [c for c in containers if c["status"] == "Running"]

    if not containers:
        console.print("[dim]No containers running.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Image")

    for c in containers:
        color = STATUS_COLORS.get(c["status"], "white")
        table.add_row(c["name"], f"[{color}]{c['status']}[/{color}]", c["image"])

    console.print(table)
