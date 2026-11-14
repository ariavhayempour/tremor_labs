from typing import Any

from fastapi import APIRouter, Request

from tremorlab.api.errors import ApiError, not_implemented
from tremorlab.api.schemas import ErrorOut, TapDataIn, TestOutcomeOut
from tremorlab.session import (
    AnalysisUnavailableError,
    InvalidStateError,
    NotFoundError,
    TestSession,
)

router = APIRouter(prefix="/api", tags=["tests"])
ERRORS: dict[int | str, dict[str, Any]] = {404: {"model": ErrorOut}, 409: {"model": ErrorOut}}


def _session(request: Request) -> TestSession:
    session: TestSession = request.app.state.session
    return session


def _lookup_error(e: Exception) -> ApiError:
    if isinstance(e, NotFoundError):
        return ApiError(404, "not_found", "Test not found.")
    return ApiError(409, "invalid_state", "This test is not recording.")


@router.post("/tests/{test_id}/stop", responses=ERRORS)
async def stop_test(request: Request, test_id: int) -> TestOutcomeOut:
    try:
        out = _session(request).stop(test_id)
    except (NotFoundError, InvalidStateError) as e:
        raise _lookup_error(e) from e
    except AnalysisUnavailableError as e:
        raise ApiError(501, "not_implemented", "Analysis for this test is not built yet.") from e
    return TestOutcomeOut(
        test_id=out.test_id, status=out.status, fail_reason=out.fail_reason, result=out.result
    )


@router.post("/tests/{test_id}/mark", status_code=204, responses=ERRORS)
async def mark_test(request: Request, test_id: int) -> None:
    try:
        _session(request).mark(test_id)
    except (NotFoundError, InvalidStateError) as e:
        raise _lookup_error(e) from e


@router.post("/tests/{test_id}/tap-data", responses=ERRORS)
def tap_data(test_id: int, body: TapDataIn) -> TestOutcomeOut:
    not_implemented()
