from .models import Organization
from .config import get_settings


def seed_default_org(session) -> Organization:
    settings = get_settings()
    existing = session.query(Organization).order_by(Organization.created_at.asc()).first()
    if existing:
        return existing
    org = Organization(name=settings.default_org_name)
    session.add(org)
    session.commit()
    session.refresh(org)
    return org
