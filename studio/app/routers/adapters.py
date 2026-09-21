from fastapi import APIRouter, Query

from ..adapters.catalog import CATALOG
from ..adapters.registry import resolve_adapter_name
from ..config import get_settings
from ..deps import UserDep
from ..schemas import AdapterCatalogOut, AdapterSlotOut

router = APIRouter(tags=["adapters"])


@router.get("/api/adapters", response_model=AdapterCatalogOut)
def list_adapters(_user: UserDep) -> AdapterCatalogOut:
    cfg = get_settings()
    return AdapterCatalogOut(
        adapters=[AdapterSlotOut(**slot.as_dict()) for slot in CATALOG],
        still_default=resolve_adapter_name("still-sheet", cfg),
        clip_default=resolve_adapter_name("clip-hop1", cfg),
    )
