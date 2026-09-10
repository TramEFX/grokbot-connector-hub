"""In-process adapter for tests and `gch demo`."""

from __future__ import annotations

import logging
from pathlib import Path

from .. import mailbox

log = logging.getLogger("gch.mock")


class MockAdapter:
    name = "mock"

    def __init__(self, port: dict, data_dir: Path, on_job):
        self.port = port
        self.data_dir = data_dir
        self.on_job = on_job
        self.submitted: list[tuple[str, str]] = []
        self.failed: list[tuple[str, str]] = []

    def start(self) -> None:
        log.info("mock adapter on %s", self.port["id"])

    def stop(self) -> None:
        return

    def inject(self, prompt: str, job_id: str = "mock-1", budget_seconds: float = 480) -> dict:
        job = mailbox.put(
            self.port["id"],
            {
                "id": job_id,
                "prompt": prompt,
                "budget_seconds": budget_seconds,
                "session_id": "mock",
            },
            self.data_dir,
        )
        self.on_job(job)
        return job

    def submit(self, job_id: str, reply: str) -> None:
        self.submitted.append((job_id, reply))

    def fail(self, job_id: str, error: str) -> None:
        self.failed.append((job_id, error))
