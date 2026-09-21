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


def _mark_default(session, org: Organization) -> Organization:
    if org.is_default:
        return org
    flagged = session.query(Organization).filter(Organization.is_default.is_(True)).first()
    if flagged:
        return flagged
    org.is_default = True
    session.commit()
    session.refresh(org)
    return org


def seed_default_org(session) -> Organization:
    """Keep the first org as the local-dev default. Extra orgs are Phase 7 multi-org lite."""
    settings = get_settings()
    flagged = session.query(Organization).filter(Organization.is_default.is_(True)).first()
    if flagged:
        seed_default_producer(session, flagged)
        return flagged
    existing = session.query(Organization).order_by(Organization.created_at.asc()).first()
    if existing:
        existing = _mark_default(session, existing)
        seed_default_producer(session, existing)
        return existing
    org = Organization(name=settings.default_org_name, is_default=True)
    session.add(org)
    session.commit()
    session.refresh(org)
    seed_default_producer(session, org)
    return org
