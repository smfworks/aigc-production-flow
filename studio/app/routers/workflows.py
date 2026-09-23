"""Import and list role-tagged Comfy workflows. Nothing here queues a render."""

from fastapi import APIRouter

from ..rbac import MutateUser, ReadUser
from ..schemas import WorkflowRegisterIn
from ..workflows import get_workflow, list_workflows, register_workflow

router = APIRouter(tags=["workflows"])


@router.get("/api/workflows")
def workflows(_user: ReadUser) -> list[dict]:
    return list_workflows()


@router.get("/api/workflows/{workflow_id}")
def workflow(workflow_id: str, _user: ReadUser) -> dict:
    return get_workflow(workflow_id)


@router.post("/api/workflows")
def import_workflow(body: WorkflowRegisterIn, _user: MutateUser) -> dict:
    return register_workflow(body.name, body.graph)
