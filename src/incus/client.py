"""Simple Incus client using httpx with Unix socket transport."""

from __future__ import annotations

import httpx


class IncusClient:
    """A simple client for the Incus REST API over Unix socket."""

    def __init__(self, socket_path: str = "/var/lib/incus/unix.socket"):
        self.socket_path = socket_path
        self.base_url = "http://incus"  # Arbitrary hostname for Unix socket
        self.transport = httpx.HTTPTransport(uds=socket_path)

    def _client(self) -> httpx.Client:
        """Create a new httpx client with Unix socket transport."""
        return httpx.Client(transport=self.transport, base_url=self.base_url)

    def get(self, path: str, **kwargs) -> httpx.Response:
        """Make a GET request to the Incus API."""
        with self._client() as client:
            return client.get(path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        """Make a POST request to the Incus API."""
        with self._client() as client:
            return client.post(path, **kwargs)

    def put(self, path: str, **kwargs) -> httpx.Response:
        """Make a PUT request to the Incus API."""
        with self._client() as client:
            return client.put(path, **kwargs)

    def delete(self, path: str, **kwargs) -> httpx.Response:
        """Make a DELETE request to the Incus API."""
        with self._client() as client:
            return client.delete(path, **kwargs)
