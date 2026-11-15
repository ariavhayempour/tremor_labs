"""FastAPI app factory; run with `uvicorn tremorlab.main:create_app --factory`."""

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tremorlab.analysis import Analyzers
from tremorlab.api import (
    routes_checks,
    routes_health,
    routes_insights,
    routes_led,
    routes_report,
    routes_settings,
    routes_sim,
    routes_tests,
    ws,
)
from tremorlab.api.errors import install_error_handlers
from tremorlab.config import Config, load_config
from tremorlab.db.connection import connect
from tremorlab.db.queries import fail_stale_recordings
from tremorlab.session import DEFAULT_ANALYZERS, TestSession
from tremorlab.sources import make_source
from tremorlab.sources.base import SensorSource
from tremorlab.sources.board_analysis import board_analyzers
from tremorlab.stream.broadcaster import Broadcaster

log = logging.getLogger(__name__)


def default_analyzers_for(config: Config) -> Analyzers:
    """With the real board, signal analysis runs on the board; sim and replay analyze locally."""
    if config.sensor_source == "board":
        return board_analyzers(config.board_host, config.board_analysis_port)
    return DEFAULT_ANALYZERS


def create_app(
    config: Config | None = None,
    *,
    source: SensorSource | None = None,
    analyzers: Analyzers | None = None,
    clock: Callable[[], float] | None = None,
) -> FastAPI:
    """Keyword overrides (source, analyzers, clock) let tests drive the stream themselves."""
    config = config or load_config()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        conn = connect(config.db_path)
        interrupted = fail_stale_recordings(conn)
        if interrupted:
            log.warning("marked %d leftover recording(s) as interrupted", interrupted)
        live = source or make_source(config)
        await live.start()
        broadcaster = Broadcaster(live)
        session = TestSession(
            conn,
            broadcaster,
            live,
            analyzers=analyzers or default_analyzers_for(config),
            clock=clock or time.time,
        )
        app.state.conn = conn
        app.state.source = live
        app.state.broadcaster = broadcaster
        app.state.session = session
        tasks = [
            asyncio.create_task(broadcaster.run(), name="broadcaster"),
            asyncio.create_task(session.run(), name="session-tick"),
        ]
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await live.stop()
            conn.close()

    app = FastAPI(title="Tremor Lab", lifespan=lifespan)
    app.state.config = config
    app.state.clock = clock or time.time
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[config.cors_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    for module in (
        routes_health,
        routes_checks,
        routes_tests,
        routes_insights,
        routes_settings,
        routes_led,
        routes_report,
        ws,
    ):
        app.include_router(module.router)
    if config.sensor_source == "sim":
        app.include_router(routes_sim.router)
    return app
