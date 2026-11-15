from fastapi import APIRouter, Request

from tremorlab.api.schemas import HealthOut, SensorsDetected
from tremorlab.config import Config
from tremorlab.sources.base import SensorSource

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health(request: Request) -> HealthOut:
    config: Config = request.app.state.config
    source: SensorSource = request.app.state.source
    h = source.health()
    return HealthOut(
        status="ok",
        sensor_source=config.sensor_source,
        connected=h.connected,
        sensors_detected=SensorsDetected(
            movement=h.sensors_detected.get("movement", False),
            distance=h.sensors_detected.get("distance", False),
        ),
        imu_hz=h.imu_hz,
        tof_hz=h.tof_hz,
    )
