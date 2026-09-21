from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database as database_module
from .adapters import resolve_adapter_name
from .config import get_settings
from .database import Base, get_db
from .deps import DbDep, UserDep
from .jobs.worker import start_worker, stop_worker
from .models import Organization
from .routers import comments, episodes, jobs, media, packs, preview, projects, review, shots
from .schemas import MetaOut, OrganizationOut, UserOut
from .seed import seed_default_org

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
        version="0.3.0",
        description=(
            "Phase 3 studio spine for the AIGC production flow. "
            "Pack zip remains the collaboration contract. "
            "Auth is a local-dev API token — SSO is not in this phase. "
            "This is not multi-tenant SaaS security. "
            "Jobs run in-process (thread worker). Celery is the documented upgrade path, not this process. "
            "The default adapter is stub — it never claims H3 or Qwen ran."
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

    @application.get("/", tags=["meta"])
    def root() -> dict:
        return {
            "name": "AIGC Studio Spine",
            "phase": 3,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "auth": "local-dev Bearer token",
            "sso": "later",
            "job_worker": "in-process thread (Celery later)",
            "adapter": "stub unless STUDIO_*_ADAPTER live hook is set",
        }

    @application.get("/health", tags=["meta"])
    def health() -> dict:
        return {"ok": True}

    @application.get("/api/meta", response_model=MetaOut, tags=["meta"])
    def meta() -> MetaOut:
        cfg = get_settings()
        return MetaOut(
            pack_builder_url=cfg.pack_builder_url,
            default_user=cfg.default_user,
            job_worker=cfg.job_worker,
            still_adapter=resolve_adapter_name("still-sheet", cfg),
            clip_adapter=resolve_adapter_name("clip-hop1", cfg),
        )

    @application.get("/api/me", response_model=UserOut, tags=["meta"])
    def me(user: UserDep) -> UserOut:
        return user

    @application.get("/api/orgs", response_model=list[OrganizationOut], tags=["meta"])
    def list_orgs(_user: UserDep, db: DbDep) -> list[OrganizationOut]:
        rows = db.query(Organization).order_by(Organization.created_at.asc()).all()
        return [OrganizationOut.model_validate(row) for row in rows]

    return application


app = create_app()
