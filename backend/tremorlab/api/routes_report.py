"""Doctor report: every dashboard insight for one window, in one response."""

from fastapi import APIRouter, Request

from tremorlab.analysis import insights
from tremorlab.api import routes_insights as ri
from tremorlab.api.schemas import ReportOut, ReportPeriod
from tremorlab.db import queries

router = APIRouter(prefix="/api", tags=["report"])


@router.get("/report")
async def report(request: Request, days: int = ri.DAYS) -> ReportOut:
    conn, w = ri.db_conn(request), ri.window(request, days)
    rows = ri.load(conn, w)
    rest = ri.rest_strength_obs(rows)
    bins = insights.dose_response(rest)
    completed = queries.completed_check_times(conn, w.start, w.now)
    return ReportOut(
        period=ReportPeriod(start=w.start, end=w.now),
        checks_completed=len(completed),
        dose_response=ri.bins_out(bins),
        returns_after_h=ri.returns_after(bins, rest),
        profile=ri.profile_rows(rows, w),
        daily=ri.daily(rest, w),
        generated_at=w.now,
    )
