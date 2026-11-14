from fastapi import APIRouter

from tremorlab.api.errors import not_implemented
from tremorlab.api.schemas import LedRequest

router = APIRouter(prefix="/api", tags=["led"])


@router.post("/led", status_code=204)
def led(body: LedRequest) -> None:
    not_implemented()
