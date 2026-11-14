from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, Request

from tremorlab.api.errors import ApiError
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
from tremorlab.api.summary import check_summary, to_check_out
from tremorlab.db import queries
from tremorlab.doses import resolve_dose
from tremorlab.session import ActiveTestError, NotFoundError, TestSession

router = APIRouter(prefix="/api", tags=["checks"])
NOT_FOUND: dict[int | str, dict[str, Any]] = {404: {"model": ErrorOut}}


def _session(request: Request) -> TestSession:
    session: TestSession = request.app.state.session
    return session


@router.post("/checks", status_code=201)
async def create_check(request: Request, body: CheckInRequest) -> CheckCreated:
    session = _session(request)
    now = session.now()
    try:
        dose_id, minutes = resolve_dose(session.conn, now, body.medication, body.hours_ago)
    except ValueError as e:
        raise ApiError(422, "validation_error", f"hours_ago: {e}") from e
    check_id = queries.insert_check(
        session.conn,
        created_at=now,
        minutes_since_dose=minutes,
        caffeine=body.caffeine,
        sleep_quality=body.sleep_quality,
        stress=body.stress,
        alcohol=body.alcohol,
        notes=body.notes,
        dose_id=dose_id,
    )
    return CheckCreated(check_id=check_id, minutes_since_dose=minutes)


@router.get("/checks")
async def list_checks(
    request: Request,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
) -> list[CheckOut]:
    conn = _session(request).conn
    rows = reversed(queries.list_checks(conn, from_, to))
    return [to_check_out(conn, c, queries.tests_for_check(conn, c.id)) for c in rows]


@router.get("/checks/{check_id}", responses=NOT_FOUND)
async def get_check(request: Request, check_id: int) -> CheckSummaryOut:
    conn = _session(request).conn
    check = queries.get_check(conn, check_id)
    if check is None:
        raise ApiError(404, "not_found", "Check not found.")
    return check_summary(conn, check)


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
async def list_doses(
    request: Request,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
) -> list[DoseOut]:
    doses = queries.list_doses(_session(request).conn, from_, to)
    return [DoseOut(id=d.id, taken_at=d.taken_at, label=d.label) for d in doses]
