"""Async support for Typer.

Workaround for https://github.com/fastapi/typer/issues/950
"""

import asyncio
import inspect
from functools import partial, wraps
from typing import Any, Callable

import typer


class AsyncTyper(typer.Typer):
    """Typer subclass with async command support."""

    @staticmethod
    def maybe_run_async(decorator: Callable, func: Callable) -> Any:
        """Wrap async functions to run with asyncio.run()."""
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            def runner(*args: Any, **kwargs: Any) -> Any:
                return asyncio.run(func(*args, **kwargs))

            decorator(runner)
        else:
            decorator(func)
        return func

    def callback(self, *args: Any, **kwargs: Any) -> Any:
        """Override callback to support async functions."""
        decorator = super().callback(*args, **kwargs)
        return partial(self.maybe_run_async, decorator)

    def command(self, *args: Any, **kwargs: Any) -> Any:
        """Override command to support async functions."""
        decorator = super().command(*args, **kwargs)
        return partial(self.maybe_run_async, decorator)
