from fastapi import APIRouter, Request

from tremorlab.api.schemas import HealthOut, SensorsDetected
from tremorlab.config import Config

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(request: Request) -> HealthOut:
    config: Config = request.app.state.config
    # Static until the broadcaster exposes the live source's health.
    return HealthOut(
        status="ok",
        sensor_source=config.sensor_source,
        connected=True,
        sensors_detected=SensorsDetected(movement=True, distance=True),
        imu_hz=None,
        tof_hz=None,
    )
