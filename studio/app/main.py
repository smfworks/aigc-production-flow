from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database as database_module
from .adapters.catalog import CATALOG
from .adapters.registry import resolve_adapter_name
from .auth import _mode, _sso_note
from .budget import DISCLAIMER
from .config import get_settings
from .database import Base, get_db
from .deps import DbDep, UserDep
from .jobs.modes import WORKER_CELERY, normalize_worker
from .jobs.worker import start_worker, stop_worker
from .models import Organization
from .oidc import oidc_configured
from .rbac import attach_role
from .routers import (
    adapters,
    audit,
    budget,
    comments,
    episodes,
    export,
    jobs,
    media,
    members,
    packs,
    presence,
    preview,
    projects,
    retention,
    review,
    shots,
    templates,
)
from .schemas import MetaOut, OrganizationOut, UserOut
from .seed import seed_default_org
from .store import active_backend, media_note, requested_backend, s3_ready

# Import models so metadata.create_all sees every table.
from . import models as _models  # noqa: F401


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=database_module.engine)
    database_module.ensure_schema(database_module.engine)
    db = next(get_db())
    try:
        seed_default_org(db)
    finally:
        db.close()
    worker = start_worker()
    if worker:
        _app.state.job_worker = worker
    yield
    stop_worker()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AIGC Studio Spine",
        version="0.6.0",
        description=(
            "Phase 6 studio spine for the AIGC production flow. "
            "Pack zip remains the collaboration contract. "
            "App-level org roles (producer / editor / reviewer / viewer) sit on top of "
            "local-dev Bearer, optional X-Forwarded-User, or optional OIDC JWKS. "
            "OIDC and Celery are opt-in and off by default. This is not a production IdP. "
            "This is not multi-tenant SaaS security. "
            "Default jobs run in-process (thread worker). "
            "Adapter catalog: stub plus documented slots (comfy-h3, comfy-qwen, webhook, cli). "
            "Budget units come from an operator rate table — not a cloud invoice. "
            "Media defaults to local disk; S3/MinIO is opt-in and never claimed live when unset. "
            "generate-ok requires gates + hop-1 receipts + a reviewer/producer sign-off "
            "(producer override is audited)."
        ),
        license_info={"name": "MIT", "identifier": "MIT"},
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(projects.router)
    application.include_router(episodes.router)
    application.include_router(packs.router)
    application.include_router(review.router)
    application.include_router(comments.router)
    application.include_router(media.router)
    application.include_router(shots.router)
    application.include_router(jobs.router)
    application.include_router(preview.router)
    application.include_router(adapters.router)
    application.include_router(budget.router)
    application.include_router(audit.router)
    application.include_router(retention.router)
    application.include_router(export.router)
    application.include_router(templates.router)
    application.include_router(members.router)
    application.include_router(presence.router)

    @application.get("/", tags=["meta"])
    def root() -> dict:
        cfg = get_settings()
        worker = normalize_worker(cfg.job_worker)
        return {
            "name": "AIGC Studio Spine",
            "phase": 6,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "auth": "local Bearer token; optional forward-header identity; optional OIDC JWKS; app-level org roles",
            "sso": _sso_note(_mode(cfg.auth_mode)),
            "job_worker": worker,
            "celery": worker == WORKER_CELERY,
            "adapters": [slot.id for slot in CATALOG],
            "media_backend": active_backend(cfg),
            "budget": DISCLAIMER,
        }

    @application.get("/health", tags=["meta"])
    def health() -> dict:
        return {"ok": True}

    @application.get("/api/meta", response_model=MetaOut, tags=["meta"])
    def meta() -> MetaOut:
        cfg = get_settings()
        worker = normalize_worker(cfg.job_worker)
        return MetaOut(
            pack_builder_url=cfg.pack_builder_url,
            default_user=cfg.default_user,
            job_worker=worker,
            still_adapter=resolve_adapter_name("still-sheet", cfg),
            clip_adapter=resolve_adapter_name("clip-hop1", cfg),
            auth_mode=_mode(cfg.auth_mode),
            sso=_sso_note(_mode(cfg.auth_mode)),
            cost_currency=cfg.cost_currency or "credits",
            retention_days=int(cfg.retention_days or 0),
            budget_hard_stop=bool(cfg.budget_hard_stop),
            media_backend=active_backend(cfg),
            media_s3_configured=requested_backend(cfg) == "s3" and s3_ready(cfg),
            media_note=media_note(cfg),
            presence_ttl_seconds=int(cfg.presence_ttl_seconds or 60),
            celery_enabled=worker == WORKER_CELERY,
            oidc_configured=oidc_configured(cfg),
            oidc_apply_role_claim=bool(cfg.oidc_apply_role_claim),
        )

    @application.get("/api/me", response_model=UserOut, tags=["meta"])
    def me(user: UserDep, db: DbDep) -> UserOut:
        return attach_role(user, db, required=False)

    @application.get("/api/orgs", response_model=list[OrganizationOut], tags=["meta"])
    def list_orgs(user: UserDep, db: DbDep) -> list[OrganizationOut]:
        # Membership is not required to see the default org name; mutating it is.
        _ = user
        rows = db.query(Organization).order_by(Organization.created_at.asc()).all()
        return [OrganizationOut.model_validate(row) for row in rows]

    return application


app = create_app()
