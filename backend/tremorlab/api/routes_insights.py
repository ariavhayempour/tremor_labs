from fastapi import APIRouter, Query

from tremorlab.api.errors import not_implemented
from tremorlab.api.schemas import DoseResponseOut, FactorEffect, InsightsSummary, ProfileRow

router = APIRouter(prefix="/api/insights", tags=["insights"])
DAYS = Query(default=14, ge=1, le=365)


@router.get("/dose-response")
def dose_response(days: int = DAYS) -> DoseResponseOut:
    not_implemented()


@router.get("/factors")
def factors(days: int = DAYS) -> list[FactorEffect]:
    not_implemented()


@router.get("/profile")
def profile(days: int = DAYS) -> list[ProfileRow]:
    not_implemented()


@router.get("/summary")
def summary(days: int = DAYS) -> InsightsSummary:
    not_implemented()
