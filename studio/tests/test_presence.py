from datetime import timedelta

from app.models import utcnow
from app.presence import heartbeat, list_active
from tests.helpers import add_member, as_user, create_episode


def test_presence_heartbeat_and_list(client, auth):
    _, episode = create_episode(client, auth, "Presence")
    beat = client.post(
        f"/api/episodes/{episode['id']}/presence",
        headers=auth,
        json={"shot_id": None},
    )
    assert beat.status_code == 200, beat.text
    names = {row["user_name"] for row in beat.json()}
    assert "tester" in names
    listed = client.get(f"/api/episodes/{episode['id']}/presence", headers=auth)
    assert listed.status_code == 200
    assert listed.json()[0]["ttl_seconds"] >= 5
    assert listed.json()[0]["role"] == "producer"


def test_presence_ttl_expires(client, auth):
    _, episode = create_episode(client, auth, "Presence TTL")
    from app.database import SessionLocal
    from app.config import get_settings

    session = SessionLocal()
    try:
        heartbeat(
            session,
            episode_id=episode["id"],
            user_name="tester",
            role="producer",
        )
        now = utcnow()
        active = list_active(session, episode["id"], now=now, settings=get_settings())
        assert any(row.user_name == "tester" for row in active)
        expired = list_active(
            session,
            episode["id"],
            now=now + timedelta(seconds=get_settings().presence_ttl_seconds + 5),
            settings=get_settings(),
        )
        assert expired == []
    finally:
        session.close()


def test_presence_includes_other_members(client, auth):
    _, episode = create_episode(client, auth, "Presence members")
    add_member(client, auth, "ed", "editor")
    client.post(f"/api/episodes/{episode['id']}/presence", headers=auth, json={})
    other = client.post(
        f"/api/episodes/{episode['id']}/presence",
        headers=as_user(auth, "ed"),
        json={},
    )
    assert other.status_code == 200
    names = {row["user_name"] for row in other.json()}
    assert names == {"tester", "ed"}
