import logging

from fastapi import APIRouter, Request

from tremorlab.api.schemas import LedRequest
from tremorlab.sources.base import SensorSource

router = APIRouter(prefix="/api", tags=["led"])
log = logging.getLogger(__name__)


@router.post("/led", status_code=204)
async def led(body: LedRequest, request: Request) -> None:
    source: SensorSource = request.app.state.source
    try:
        await source.led(body.command, body.value)
    except Exception:
        # LEDs are never on the critical path: log and still answer 204.
        log.warning("led %s %s failed", body.command, body.value, exc_info=True)
