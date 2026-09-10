"""Adapter interface. Agensis is first; others plug the same mailbox."""

from __future__ import annotations

from typing import Protocol


class Adapter(Protocol):
    name: str

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def submit(self, job_id: str, reply: str) -> None: ...
    def fail(self, job_id: str, error: str) -> None: ...


def load_adapter(name: str, port: dict, data_dir, on_job):
    if name == "agensis":
        from .agensis import AgensisAdapter

        return AgensisAdapter(port, data_dir, on_job)
    if name == "mock":
        from .mock import MockAdapter

        return MockAdapter(port, data_dir, on_job)
    raise ValueError("unknown adapter: %s" % name)
