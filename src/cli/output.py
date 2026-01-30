"""Console output helpers with scoped indentation."""

from contextlib import contextmanager
from typing import Iterator

from rich.console import Console


class Output:
    """Console output helpers with scoped indentation.

    Usage:
        out = Output()
        out.section("Starting process...")
        with out.indent():
            out.info("Step 1")
            with out.indent():
                out.success("Done")
    """

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self._indent_level = 0

    @property
    def _prefix(self) -> str:
        return " " * self._indent_level

    @contextmanager
    def indent(self, spaces: int = 2) -> Iterator[None]:
        """Context manager for scoped indentation."""
        self._indent_level += spaces
        try:
            yield
        finally:
            self._indent_level -= spaces

    @contextmanager
    def operation(self, title: str, color: str = "blue") -> Iterator[None]:
        """Print a section header and indent the block."""
        self.section(title, color)
        with self.indent():
            yield

    def error(self, msg: str) -> None:
        """Print an error message in red."""
        self.console.print(f"{self._prefix}[red]Error:[/red] {msg}")

    def warning(self, msg: str) -> None:
        """Print a warning message in yellow."""
        self.console.print(f"{self._prefix}[yellow]Warning:[/yellow] {msg}")

    def hint(self, msg: str) -> None:
        """Print a hint message in yellow."""
        self.console.print(f"{self._prefix}[yellow]Hint:[/yellow] {msg}")

    def success(self, msg: str) -> None:
        """Print a success message with green checkmark."""
        self.console.print(f"{self._prefix}[green]✓[/green] {msg}")

    def failure(self, msg: str) -> None:
        """Print a failure message with red X."""
        self.console.print(f"{self._prefix}[red]✗[/red] {msg}")

    def section(self, title: str, color: str = "blue") -> None:
        """Print a bold section header."""
        self.console.print(f"{self._prefix}[bold {color}]{title}[/bold {color}]")

    def dim(self, msg: str) -> None:
        """Print a dimmed message."""
        self.console.print(f"{self._prefix}[dim]{msg}[/dim]")

    def info(self, msg: str) -> None:
        """Print an info message (no special formatting)."""
        self.console.print(f"{self._prefix}{msg}")

    def styled(self, msg: str) -> None:
        """Print a message with Rich markup (caller handles formatting)."""
        self.console.print(f"{self._prefix}{msg}")


# Module-level instance for convenience
out = Output()
