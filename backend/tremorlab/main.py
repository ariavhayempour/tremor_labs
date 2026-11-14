"""FastAPI app factory; run with `uvicorn tremorlab.main:create_app --factory`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


def create_app(config: Config | None = None) -> FastAPI:
    config = config or load_config()
    app = FastAPI(title="Tremor Lab")
    app.state.config = config
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
