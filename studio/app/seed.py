from .config import get_settings
from .models import ROLE_PRODUCER, Organization, OrgMember


def seed_default_producer(session, org: Organization) -> OrgMember:
    settings = get_settings()
    name = (settings.default_user or "local-dev").strip() or "local-dev"
    member = (
        session.query(OrgMember)
        .filter(OrgMember.organization_id == org.id, OrgMember.user_name == name)
        .first()
    )
    if member:
        return member
    member = OrgMember(organization_id=org.id, user_name=name, role=ROLE_PRODUCER)
    session.add(member)
    session.commit()
    session.refresh(member)
    return member


def seed_default_org(session) -> Organization:
    settings = get_settings()
    existing = session.query(Organization).order_by(Organization.created_at.asc()).first()
    if existing:
        seed_default_producer(session, existing)
        return existing
    org = Organization(name=settings.default_org_name)
    session.add(org)
    session.commit()
    session.refresh(org)
    seed_default_producer(session, org)
    return org
