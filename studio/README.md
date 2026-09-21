# AIGC studio API (Phase 1)

FastAPI spine for projects, episodes, pack zip revisions, review states, comments, and a local media store.

Operator docs: [../docs/STUDIO.md](../docs/STUDIO.md).

```bash
# from repo root
./scripts/dev-studio.sh api
```

OpenAPI: http://localhost:8000/docs

Auth is **local-dev only** (`Authorization: Bearer $STUDIO_API_TOKEN`). SSO is not in this phase.
