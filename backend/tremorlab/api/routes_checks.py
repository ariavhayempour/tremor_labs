from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, Request

from tremorlab.api.errors import ApiError, not_implemented
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
from tremorlab.db import queries
from tremorlab.session import ActiveTestError, NotFoundError, TestSession

router = APIRouter(prefix="/api", tags=["checks"])
NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"model": ErrorOut}}


def _session(request: Request) -> TestSession:
    session: TestSession = request.app.state.session
    return session


@router.post("/checks", status_code=201)
async def create_check(request: Request, body: CheckInRequest) -> CheckCreated:
    session = _session(request)
    # Dose logging is not wired yet, so no check is linked to a dose.
    check_id = queries.insert_check(
        session.conn,
        created_at=session.now(),
        minutes_since_dose=None,
        caffeine=body.caffeine,
        sleep_quality=body.sleep_quality,
        stress=body.stress,
        alcohol=body.alcohol,
        notes=body.notes,
        dose_id=None,
    )
    return CheckCreated(check_id=check_id, minutes_since_dose=None)


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
async def start_test(request: Request, check_id: int, body: StartTestRequest) -> TestStarted:
    try:
        test_id = _session(request).start(check_id, body.type, body.hand)
    except NotFoundError as e:
        raise ApiError(404, "not_found", "Check not found.") from e
    except ActiveTestError as e:
        raise ApiError(409, "test_active", "A test is already recording.") from e
    return TestStarted(test_id=test_id)


@router.get("/doses")
def list_doses(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
) -> list[DoseOut]:
    not_implemented()
