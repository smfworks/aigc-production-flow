from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database as database_module
from .config import get_settings
from .database import Base, get_db
from .deps import DbDep, UserDep
from .models import Organization
from .routers import comments, episodes, media, packs, projects, review, shots
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
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AIGC Studio Spine",
        version="0.1.0",
        description=(
            "Phase 2 studio spine for the AIGC production flow. "
            "Pack zip remains the collaboration contract. "
            "Auth is a local-dev API token — SSO is not in this phase. "
            "This is not multi-tenant SaaS security. "
            "Async generate jobs are deferred to Phase 3."
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

    @application.get("/", tags=["meta"])
    def root() -> dict:
        return {
            "name": "AIGC Studio Spine",
            "phase": 2,
            "docs": "/docs",
            "openapi": "/openapi.json",
            "auth": "local-dev Bearer token",
            "sso": "later",
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
