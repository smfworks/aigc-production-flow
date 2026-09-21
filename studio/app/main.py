from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy import text

from . import database as database_module
from .adapters.catalog import CATALOG
from .adapters.health import catalog_health
from .adapters.registry import resolve_adapter_name
from .auth import _mode, _sso_note
from .budget import DISCLAIMER
from .config import get_settings
from .database import Base, get_db
from .deps import DbDep, ScopedUserDep
from .jobs.modes import WORKER_CELERY, normalize_worker
from .jobs.worker import start_worker, stop_worker
from .models import Job
from .notify import webhook_configured
from .observability import StructuredLogMiddleware, prometheus_text
from .oidc import oidc_configured
from .rbac import role_matrix
from .routers import (
    adapters,
    audit,
    backup,
    budget,
    comments,
    continuity,
    demo,
    episodes,
    export,
    handoffs,
    identity,
    jobs,
    media,
    members,
    notifications,
    orgs,
    packs,
    presence,
    preview,
    projects,
    retention,
    review,
    shots,
    templates,
)
from .schemas import MetaOut, UserOut
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
        version="0.9.0",
        description=(
            "Phase 9 studio spine for the AIGC production flow. "
            "Pack zip remains the collaboration contract. "
            "App-level roles add writer and art beside the Phase 5 producer / editor / "
            "reviewer / viewer bundle. Episode season/sequence order, a soft playlist "
            "scrubber, and identity unapprove/keyword edit. "
            "Visual identity store (approved sheets + per-window plates). "
            "Pack revision diff before import overwrite. Distinct entity-schedule rows "
            "are not collapsed. "
            "Builder Open in Studio can stage a zip for auto-import after episode pick. "
            "comfy-h3 / comfy-qwen declare measured window metadata; unset hooks are not live. "
            "Multi-org lite: membership isolation, not SaaS billing, not SSO org mapping. "
            "Roles stay app-level unless STUDIO_OIDC_APPLY_ROLE_CLAIM is set. "
            "OIDC and Celery are opt-in and off by default. This is not a production IdP. "
            "Default jobs run in-process (thread worker). "
            "Adapter catalog: stub plus documented slots (comfy-h3, comfy-qwen, webhook, cli). "
            "Budget units come from an operator rate table — not a cloud invoice. "
            "Media defaults to local disk; S3/MinIO is opt-in and never claimed live when unset. "
            "generate-ok requires gates + hop-1 receipts + a reviewer/producer sign-off "
            "(producer override is audited). Live adapters must not skip hop-1 watch. "
            "Optional notify webhook is unset by default. /metrics is a tiny Prometheus scrape, not APM."
        ),
        license_info={"name": "MIT", "identifier": "MIT"},
        lifespan=lifespan,
    )
    application.add_middleware(StructuredLogMiddleware)
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
    application.include_router(handoffs.router)
    application.include_router(identity.router)
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
    application.include_router(orgs.router)
    application.include_router(notifications.router)
    application.include_router(continuity.router)
    application.include_router(demo.router)
    application.include_router(backup.router)

    @application.get("/", tags=["meta"])
    def root() -> dict:
        cfg = get_settings()
        worker = normalize_worker(cfg.job_worker)
        return {
            "name": "AIGC Studio Spine",
            "phase": 9,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "auth": "local Bearer token; optional forward-header identity; optional OIDC JWKS; app-level org roles",
            "sso": _sso_note(_mode(cfg.auth_mode)),
            "multi_org": "lite — membership isolation, not SaaS billing",
            "job_worker": worker,
            "celery": worker == WORKER_CELERY,
            "adapters": [slot.id for slot in CATALOG],
            "media_backend": active_backend(cfg),
            "notify_webhook_configured": webhook_configured(cfg),
            "budget": DISCLAIMER,
        }

    @application.get("/health", tags=["meta"])
    def health() -> dict:
        return {"ok": True}

    @application.get("/healthz", tags=["meta"])
    def healthz() -> dict:
        return {"ok": True, "live": True}

    @application.get("/readyz", tags=["meta"])
    def readyz() -> dict:
        cfg = get_settings()
        worker = normalize_worker(cfg.job_worker)
        db_ok = False
        detail = ""
        session = next(get_db())
        try:
            session.execute(text("SELECT 1"))
            db_ok = True
        except Exception as exc:  # noqa: BLE001 — readiness must not raise
            detail = str(exc)
        finally:
            session.close()
        body = {
            "ok": db_ok,
            "db": db_ok,
            "job_worker": worker,
            "celery": worker == WORKER_CELERY,
            "note": "DB reachable + worker mode reported. Celery/S3/OIDC are not required for ready.",
        }
        if detail:
            body["detail"] = detail
        if not db_ok:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=503, content=body)
        return body

    @application.get("/metrics", tags=["meta"], response_class=PlainTextResponse)
    def metrics() -> str:
        session = next(get_db())
        try:
            queued = session.query(Job).filter(Job.status == "queued").count()
            running = session.query(Job).filter(Job.status == "running").count()
        finally:
            session.close()
        health_rows = catalog_health()
        return prometheus_text(
            job_queued=queued,
            job_running=running,
            adapter_health=health_rows,
        )

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
            notify_webhook_configured=webhook_configured(cfg),
            multi_org=True,
            role_matrix=role_matrix(),
        )

    @application.get("/api/me", response_model=UserOut, tags=["meta"])
    def me(user: ScopedUserDep) -> UserOut:
        return user

    return application


app = create_app()
