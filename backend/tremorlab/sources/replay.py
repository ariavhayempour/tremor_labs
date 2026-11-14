"""ReplaySource: re-emits stored raw_samples in real time, shifted to now, looping."""

import sqlite3
import time
from collections.abc import AsyncIterator, Callable

from tremorlab.config import Config
from tremorlab.sources.base import Batch, LedCommand, SourceHealth


class ReplaySource:
    name = "replay"

    def __init__(
        self,
        conn: sqlite3.Connection,
        test_ids: list[int],
        *,
        fast: bool = False,
        clock: Callable[[], float] = time.time,
    ) -> None:
        raise NotImplementedError

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    def batches(self) -> AsyncIterator[Batch]:
        raise NotImplementedError

    async def led(self, command: LedCommand, value: int | None) -> None:
        raise NotImplementedError

    def health(self) -> SourceHealth:
        raise NotImplementedError


def make_replay_source(config: Config) -> ReplaySource:
    """Replay config.replay_test_id, else the latest check with done rest, posture and reach."""
    raise NotImplementedError
