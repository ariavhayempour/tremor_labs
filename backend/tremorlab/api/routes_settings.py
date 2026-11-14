from fastapi import APIRouter

from tremorlab.api.errors import not_implemented
from tremorlab.api.schemas import SettingsModel, SettingsUpdate

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
def get_settings() -> SettingsModel:
    not_implemented()


@router.put("/settings")
def put_settings(body: SettingsUpdate) -> SettingsModel:
    not_implemented()
