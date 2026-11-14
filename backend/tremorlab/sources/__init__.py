"""Sensor source selection. Imports are lazy so each source's dependencies load only when used."""

from tremorlab.config import Config
from tremorlab.sources.base import SensorSource


def make_source(config: Config) -> SensorSource:
    if config.sensor_source == "sim":
        from tremorlab.sources.simulated import SimulatedSource

        return SimulatedSource(config.sim)
    if config.sensor_source == "board":
        from tremorlab.sources.board import BoardSource

        return BoardSource(config.board_host, config.board_port)
    from tremorlab.sources.replay import make_replay_source

    return make_replay_source(config)
