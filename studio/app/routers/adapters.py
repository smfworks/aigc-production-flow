from fastapi import APIRouter, HTTPException, status

from ..adapters.catalog import CATALOG, KNOWN_IDS
from ..adapters.health import catalog_health, health_for
from ..adapters.registry import resolve_adapter_name
from ..config import get_settings
from ..rbac import ReadUser
from ..schemas import AdapterCatalogOut, AdapterHealthOut, AdapterSlotOut

router = APIRouter(tags=["adapters"])


def _slot_out(slot, health: dict | None = None) -> AdapterSlotOut:
    payload = slot.as_dict()
    if health:
        payload["health"] = AdapterHealthOut.model_validate(health)
    return AdapterSlotOut(**payload)


@router.get("/api/adapters", response_model=AdapterCatalogOut)
def list_adapters(_user: ReadUser) -> AdapterCatalogOut:
    cfg = get_settings()
    health = catalog_health(cfg)
    by_id = {row["id"]: row for row in health}
    return AdapterCatalogOut(
        adapters=[_slot_out(slot, by_id.get(slot.id)) for slot in CATALOG],
        still_default=resolve_adapter_name("still-sheet", cfg),
        clip_default=resolve_adapter_name("clip-hop1", cfg),
        health=[AdapterHealthOut.model_validate(row) for row in health],
    )


@router.get("/api/adapters/health", response_model=list[AdapterHealthOut])
def adapters_health(_user: ReadUser) -> list[AdapterHealthOut]:
    return [AdapterHealthOut.model_validate(row) for row in catalog_health()]


@router.get("/api/adapters/{adapter_id}/health", response_model=AdapterHealthOut)
def adapter_health(adapter_id: str, _user: ReadUser) -> AdapterHealthOut:
    key = (adapter_id or "").strip().lower()
    if key not in KNOWN_IDS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown adapter {adapter_id}.",
        )
    return AdapterHealthOut.model_validate(health_for(key))


@router.post("/api/adapters/{adapter_id}/dry-run", response_model=AdapterHealthOut)
def adapter_dry_run(adapter_id: str, _user: ReadUser) -> AdapterHealthOut:
    """Same as health: reachable? config present? Does not enqueue a generate job."""
    key = (adapter_id or "").strip().lower()
    if key not in KNOWN_IDS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown adapter {adapter_id}.",
        )
    return AdapterHealthOut.model_validate(health_for(key))
