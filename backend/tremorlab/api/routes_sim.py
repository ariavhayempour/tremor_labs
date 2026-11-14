from fastapi import APIRouter

from tremorlab.api.errors import not_implemented
from tremorlab.api.schemas import SimParamsOut, SimUpdateRequest

router = APIRouter(prefix="/api", tags=["sim"])


@router.get("/sim")
def get_sim() -> SimParamsOut:
    not_implemented()


@router.put("/sim")
def put_sim(body: SimUpdateRequest) -> SimParamsOut:
    not_implemented()
