from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query

from tremorlab.api.errors import not_implemented
from tremorlab.api.schemas import (
    CheckCreated,
    CheckInRequest,
    CheckOut,
    CheckSummaryOut,
    DoseOut,
    ErrorOut,
    StartTestRequest,
    TestStarted,
)

router = APIRouter(prefix="/api", tags=["checks"])
NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"model": ErrorOut}}


@router.post("/checks", status_code=201)
def create_check(body: CheckInRequest) -> CheckCreated:
    not_implemented()


@router.get("/checks")
def list_checks(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
) -> list[CheckOut]:
    not_implemented()


@router.get("/checks/{check_id}", responses=NOT_FOUND)
def get_check(check_id: int) -> CheckSummaryOut:
    not_implemented()


@router.post(
    "/checks/{check_id}/tests",
    status_code=201,
    responses={**NOT_FOUND, 409: {"model": ErrorOut}},
)
def start_test(check_id: int, body: StartTestRequest) -> TestStarted:
    not_implemented()


@router.get("/doses")
def list_doses(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
) -> list[DoseOut]:
    not_implemented()
