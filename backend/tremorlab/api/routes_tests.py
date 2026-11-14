from typing import Any

from fastapi import APIRouter

from tremorlab.api.errors import not_implemented
from tremorlab.api.schemas import ErrorOut, TapDataIn, TestOutcomeOut

router = APIRouter(prefix="/api", tags=["tests"])
ERRORS: dict[int | str, dict[str, Any]] = {404: {"model": ErrorOut}, 409: {"model": ErrorOut}}


@router.post("/tests/{test_id}/stop", responses=ERRORS)
def stop_test(test_id: int) -> TestOutcomeOut:
    not_implemented()


@router.post("/tests/{test_id}/mark", status_code=204, responses=ERRORS)
def mark_test(test_id: int) -> None:
    not_implemented()


@router.post("/tests/{test_id}/tap-data", responses=ERRORS)
def tap_data(test_id: int, body: TapDataIn) -> TestOutcomeOut:
    not_implemented()
