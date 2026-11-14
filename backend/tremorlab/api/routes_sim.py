from fastapi import APIRouter, Request

from tremorlab.api.errors import ApiError
from tremorlab.api.schemas import SimParamsOut, SimUpdateRequest
from tremorlab.config import SimParams
from tremorlab.sources.simulated import SimulatedSource

router = APIRouter(prefix="/api", tags=["sim"])


def _sim(request: Request) -> SimulatedSource:
    source = request.app.state.source
    if not isinstance(source, SimulatedSource):
        raise ApiError(404, "not_found", "The simulator is not the active sensor source.")
    return source


def _out(params: SimParams) -> SimParamsOut:
    return SimParamsOut(
        tremor_hz=params.tremor_hz,
        tremor_amp=params.tremor_amp,
        noise=params.noise,
        hand_mm=params.hand_mm,
        reach_wobble=params.reach_wobble,
    )


@router.get("/sim")
async def get_sim(request: Request) -> SimParamsOut:
    return _out(_sim(request).params)


@router.put("/sim")
async def put_sim(request: Request, body: SimUpdateRequest) -> SimParamsOut:
    source = _sim(request)
    changes = body.model_dump(exclude_none=True, exclude={"action"})
    params = source.set_params(**changes) if changes else source.params
    if body.action == "descent":
        source.trigger_descent()
    return _out(params)
