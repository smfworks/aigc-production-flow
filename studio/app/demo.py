"""Honest demo seed: vertical template + fixture media metadata.

No likeness stills. No engine MP4 claims. Gates stay red unless the template is green.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from .audit import DEMO_SEED, record
from .models import Episode, MediaAsset, Project, utcnow
from .packzip import slugify
from .store import get_store
from .verticals import create_project_from_template

DEMO_TEMPLATE_ID = "short-drama-ep"
DEMO_HONESTY = (
    "Stub demo from the short-drama-ep vertical template. Fixture media is JSON "
    "metadata only — no likeness still, no engine MP4, no fake generate-ok."
)

FIXTURE_NOTES = "fixture metadata only — no likeness still, no engine MP4"


def seed_demo(
    db: Session,
    *,
    org_id: str,
    user_name: str,
    name: str | None = None,
) -> tuple[Project, Episode, int]:
    from .routers.projects import _unique_slug

    title = (name or "Demo episode (stub)").strip() or "Demo episode (stub)"
    project, episode, _revision = create_project_from_template(
        db,
        org_id=org_id,
        template_id=DEMO_TEMPLATE_ID,
        user_name=user_name,
        name=title,
        description=DEMO_HONESTY,
        unique_slug=_unique_slug,
    )
    fixtures = [
        {
            "kind": "sheet",
            "entity_type": "character",
            "entity_label": "lead",
            "original_name": "lead-sheet.fixture.json",
            "payload": {
                "kind": "sheet",
                "entity": "lead",
                "adapter": "stub",
                "approval": "draft",
                "claim": "Fixture metadata only. No likeness still was generated.",
            },
            "lock_keywords": "lead sheet placeholder — not a likeness",
        },
        {
            "kind": "plate",
            "entity_type": "character",
            "entity_label": "lead",
            "original_name": "lead-plate.fixture.json",
            "payload": {
                "kind": "plate",
                "entity": "lead",
                "adapter": "stub",
                "approval": "draft",
                "claim": "Fixture metadata only. This is not a hop-1 frame.",
            },
            "lock_keywords": "lead plate placeholder — not a likeness",
        },
        {
            "kind": "other",
            "entity_type": "prop",
            "entity_label": "token",
            "original_name": "token.fixture.json",
            "payload": {
                "kind": "prop",
                "entity": "token",
                "adapter": "stub",
                "claim": "Fixture metadata only. Numbers still belong on the prop card.",
            },
        },
    ]
    count = 0
    for item in fixtures:
        payload = json.dumps(item["payload"], indent=2).encode("utf-8")
        asset = MediaAsset(
            episode_id=episode.id,
            kind=item["kind"],
            original_name=item["original_name"],
            stored_name="",
            content_type="application/json",
            path="",
            entity_label=item["entity_label"],
            entity_type=item["entity_type"],
            notes=FIXTURE_NOTES,
            created_by=user_name,
            lock_keywords=item.get("lock_keywords") or "",
            approval_status="draft",
        )
        db.add(asset)
        db.flush()
        stored = f"{asset.id}_{slugify(Path(item['original_name']).stem, 'fixture')}.json"
        rel = Path(episode.id) / "demo" / stored
        get_store().put(str(rel), payload)
        asset.stored_name = stored
        asset.path = str(rel)
        count += 1
    episode.synopsis = DEMO_HONESTY
    episode.updated_at = utcnow()
    project.updated_at = utcnow()
    record(
        db,
        actor=user_name,
        action=DEMO_SEED,
        organization_id=org_id,
        project_id=project.id,
        episode_id=episode.id,
        entity_type="episode",
        entity_id=episode.id,
        detail={
            "template_id": DEMO_TEMPLATE_ID,
            "fixture_media": count,
            "likeness": False,
            "engine_mp4": False,
            "fake_generate": False,
        },
    )
    return project, episode, count
