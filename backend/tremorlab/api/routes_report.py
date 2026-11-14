from fastapi import APIRouter, Query

from tremorlab.api.errors import not_implemented
from tremorlab.api.schemas import ReportOut

router = APIRouter(prefix="/api", tags=["report"])


@router.get("/report")
def report(days: int = Query(default=14, ge=1, le=365)) -> ReportOut:
    not_implemented()
