"""Operation framework for the Kapsule daemon.

Provides decorators and utilities for daemon operations that emit
progress signals over D-Bus.
"""

from __future__ import annotations

import asyncio
import functools
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import IntEnum
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Concatenate,
    ParamSpec,
    TypeVar,
)

if TYPE_CHECKING:
    from .service import KapsuleManagerInterface


P = ParamSpec("P")
R = TypeVar("R")


class MessageType(IntEnum):
    """Message types for operation progress."""

    INFO = 0  # Regular info (blue)
    SUCCESS = 1  # Success with checkmark (green)
    WARNING = 2  # Warning (yellow)
    ERROR = 3  # Error (red)
    DIM = 4  # Muted/secondary info (gray)
    HINT = 5  # Hint for user action


class OperationError(Exception):
    """Raised for expected operation failures with user-friendly messages.

    These are caught by the operation decorator and reported cleanly
    to the user, unlike unexpected exceptions which show as internal errors.
    """

    pass


@dataclass
class ProgressBar:
    """Handle for an active progress bar."""

    progress_id: str
    _reporter: "OperationReporter"

    def update(self, current: int, rate: float = 0.0) -> None:
        """Update progress bar position.

        Args:
            current: Current progress value (bytes, items, etc.)
            rate: Rate of progress (bytes/sec, etc.) for ETA calculation
        """
        self._reporter._interface.ProgressUpdate(self.progress_id, current, rate)

    def complete(self, success: bool = True, message: str = "") -> None:
        """Complete and remove the progress bar.

        Args:
            success: Whether the operation succeeded
            message: Optional message to display (replaces the bar)
        """
        self._reporter._interface.ProgressCompleted(self.progress_id, success, message)


@dataclass
class OperationReporter:
    """Injected into operations for progress reporting.

    This is the main interface operations use to report progress.
    Messages are emitted as D-Bus signals that clients can subscribe to.

    Usage in operation methods:
        async def create_container(self, progress: OperationReporter, name: str, ...):
            progress.info(f"Image: {image}")

            async with progress.track("Downloading image...", total=size) as bar:
                for chunk in download():
                    bar.update(downloaded)

            progress.success("Image downloaded")
    """

    operation_id: str
    _interface: "KapsuleManagerInterface"
    _indent: int = 1  # Default indent for messages within operation

    def info(self, message: str, indent: int | None = None) -> None:
        """Emit an info message."""
        self._interface.OperationMessage(
            self.operation_id,
            int(MessageType.INFO),
            message,
            indent if indent is not None else self._indent,
        )

    def success(self, message: str, indent: int | None = None) -> None:
        """Emit a success message."""
        self._interface.OperationMessage(
            self.operation_id,
            int(MessageType.SUCCESS),
            message,
            indent if indent is not None else self._indent,
        )

    def warning(self, message: str, indent: int | None = None) -> None:
        """Emit a warning message."""
        self._interface.OperationMessage(
            self.operation_id,
            int(MessageType.WARNING),
            message,
            indent if indent is not None else self._indent,
        )

    def error(self, message: str, indent: int | None = None) -> None:
        """Emit an error message."""
        self._interface.OperationMessage(
            self.operation_id,
            int(MessageType.ERROR),
            message,
            indent if indent is not None else self._indent,
        )

    def dim(self, message: str, indent: int | None = None) -> None:
        """Emit a dimmed/secondary message."""
        self._interface.OperationMessage(
            self.operation_id,
            int(MessageType.DIM),
            message,
            indent if indent is not None else self._indent,
        )

    def hint(self, message: str, indent: int | None = None) -> None:
        """Emit a hint message."""
        self._interface.OperationMessage(
            self.operation_id,
            int(MessageType.HINT),
            message,
            indent if indent is not None else self._indent,
        )

    def start_progress(
        self,
        description: str,
        total: int = -1,
        indent: int | None = None,
    ) -> ProgressBar:
        """Start a progress bar.

        Remember to call .complete() when done, or use the track() context manager.

        Args:
            description: What's being tracked (e.g., "Downloading image...")
            total: Total units, or -1 for indeterminate
            indent: Indent level for display
        """
        progress_id = str(uuid.uuid4())
        self._interface.ProgressStarted(
            self.operation_id,
            progress_id,
            description,
            total,
            indent if indent is not None else self._indent,
        )
        return ProgressBar(progress_id, self)

    @asynccontextmanager
    async def track(
        self,
        description: str,
        total: int = -1,
        indent: int | None = None,
        success_message: str = "",
    ) -> AsyncIterator[ProgressBar]:
        """Context manager for progress tracking.

        Usage:
            async with progress.track("Downloading...", total=size) as bar:
                for chunk in data:
                    bar.update(current)

        Args:
            description: What's being tracked
            total: Total units, or -1 for indeterminate
            indent: Indent level
            success_message: Optional message on success (replaces bar)
        """
        bar = self.start_progress(description, total, indent)
        try:
            yield bar
            bar.complete(success=True, message=success_message)
        except Exception:
            bar.complete(success=False)
            raise

    def indented(self, levels: int = 1) -> "OperationReporter":
        """Return a reporter with increased indent level.

        Use for sub-operations that should appear nested in the output.

        Args:
            levels: Number of indent levels to add
        """
        return OperationReporter(
            operation_id=self.operation_id,
            _interface=self._interface,
            _indent=self._indent + levels,
        )


@dataclass
class RunningOperation:
    """Tracks a running operation."""

    id: str
    operation_type: str
    target: str
    task: asyncio.Task[None]


@dataclass
class OperationTracker:
    """Tracks all running operations in the daemon."""

    _operations: dict[str, RunningOperation] = field(default_factory=dict)

    def add(self, op: RunningOperation) -> None:
        """Register a running operation."""
        self._operations[op.id] = op

    def remove(self, op_id: str) -> None:
        """Remove a completed operation."""
        self._operations.pop(op_id, None)

    def get(self, op_id: str) -> RunningOperation | None:
        """Get an operation by ID."""
        return self._operations.get(op_id)

    def list_all(self) -> list[RunningOperation]:
        """List all running operations."""
        return list(self._operations.values())


def operation(
    operation_type: str,
    description: str,
    target_param: str = "name",
) -> Callable[
    [Callable[Concatenate[Any, OperationReporter, P], Awaitable[None]]],
    Callable[Concatenate[Any, P], Awaitable[str]],
]:
    """Decorator for daemon operations with automatic lifecycle signals.

    Wraps an async method to:
    - Generate a unique operation ID
    - Emit OperationStarted signal
    - Inject an OperationReporter as the first parameter (after self)
    - Run the operation in a background task
    - Emit OperationCompleted on success or failure
    - Handle OperationError for user-friendly error messages

    Args:
        operation_type: Type identifier (e.g., "create", "delete", "start")
        description: Template string with {param} placeholders for kwargs
        target_param: Name of the parameter that represents the target (for signals)

    Example:
        @operation("create", "Creating container: {name}")
        async def create_container(
            self,
            progress: OperationReporter,  # Auto-injected
            name: str,
            image: str,
        ) -> None:
            progress.info(f"Image: {image}")
            ...
    """

    def decorator(
        func: Callable[Concatenate[Any, OperationReporter, P], Awaitable[None]],
    ) -> Callable[Concatenate[Any, P], Awaitable[str]]:
        @functools.wraps(func)
        async def wrapper(self: Any, *args: P.args, **kwargs: P.kwargs) -> str:
            # Generate operation ID
            op_id = str(uuid.uuid4())

            # Build description from template
            desc = description.format(**kwargs)

            # Get target from kwargs
            target = str(kwargs.get(target_param, ""))

            # Create the reporter
            reporter = OperationReporter(
                operation_id=op_id,
                _interface=self._interface,
            )

            # Emit start signal
            self._interface.OperationStarted(op_id, operation_type, desc, target)

            # Run the operation in a task so we return immediately
            async def run_operation() -> None:
                try:
                    await func(self, reporter, *args, **kwargs)
                    self._interface.OperationCompleted(op_id, True, "")
                except OperationError as e:
                    # Expected errors - user-friendly message
                    self._interface.OperationCompleted(op_id, False, str(e))
                except Exception as e:
                    # Unexpected errors - log and report
                    import traceback

                    traceback.print_exc()
                    self._interface.OperationCompleted(op_id, False, f"Internal error: {e}")
                finally:
                    # Remove from tracker if present
                    if hasattr(self, "_tracker"):
                        self._tracker.remove(op_id)

            task = asyncio.create_task(run_operation(), name=f"op-{operation_type}-{op_id[:8]}")

            # Track the operation if we have a tracker
            if hasattr(self, "_tracker"):
                self._tracker.add(
                    RunningOperation(
                        id=op_id,
                        operation_type=operation_type,
                        target=target,
                        task=task,
                    )
                )

            return op_id

        return wrapper

    return decorator
