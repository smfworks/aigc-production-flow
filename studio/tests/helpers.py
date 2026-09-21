"""Shared HTTP helpers for studio Phase 3 tests."""

from __future__ import annotations

import json
import time

from tests.fixtures import green_pack, pack_zip_bytes


def as_user(auth: dict[str, str], name: str) -> dict[str, str]:
    return {**auth, "X-User-Name": name}


def org_id(client, auth) -> str:
    me = client.get("/api/me", headers=auth)
    assert me.status_code == 200
    oid = me.json().get("org_id")
    if oid:
        return oid
    orgs = client.get("/api/orgs", headers=auth)
    assert orgs.status_code == 200
    return orgs.json()[0]["id"]


def add_member(client, auth, user_name: str, role: str = "viewer") -> dict:
    oid = org_id(client, auth)
    response = client.post(
        f"/api/orgs/{oid}/members",
        headers=auth,
        json={"user_name": user_name, "role": role},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_episode(client, auth, name: str = "Phase 3"):
    project = client.post("/api/projects", json={"name": name}, headers=auth).json()
    episode = client.post(
        f"/api/projects/{project['id']}/episodes",
        json={"title": "Ep 1"},
        headers=auth,
    ).json()
    return project, episode


def import_green(client, auth, episode_id: str):
    response = client.post(
        f"/api/episodes/{episode_id}/pack",
        headers=auth,
        files={"file": ("green.zip", pack_zip_bytes(green_pack()), "application/zip")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def ready_all_shots(client, auth, episode_id: str) -> list[dict]:
    extracted = client.post(
        f"/api/episodes/{episode_id}/shots/extract-candidates",
        headers=auth,
    )
    assert extracted.status_code == 200, extracted.text
    shots = extracted.json()
    for shot in shots:
        for candidate in shot["candidates"]:
            if candidate["status"] in {"pending", "accepted"}:
                patched = client.patch(
                    f"/api/episodes/{episode_id}/shots/{shot['id']}/candidates/{candidate['id']}",
                    headers=auth,
                    json={"status": "ignored"},
                )
                assert patched.status_code == 200, patched.text
        ready = client.put(
            f"/api/episodes/{episode_id}/shots/{shot['id']}/readiness",
            headers=auth,
            json={"readiness": "ready"},
        )
        assert ready.status_code == 200, ready.text
    return client.get(f"/api/episodes/{episode_id}/shots", headers=auth).json()


def green_ready_episode(client, auth, name: str = "Phase 3"):
    project, episode = create_episode(client, auth, name)
    import_green(client, auth, episode["id"])
    shots = ready_all_shots(client, auth, episode["id"])
    return project, episode, shots


def attach_watched_receipt(
    client,
    auth,
    episode_id: str,
    shot_id: str,
    *,
    ng_reason: str = "",
    still_vs_lock: str = "Fixture still-vs-lock: T2V none+why, no engine frame.",
    watched: bool = True,
):
    payload = {
        "adapter": "stub",
        "duration_s": 10.125,
        "frames": 243,
        "fps": 24,
        "still_vs_lock": still_vs_lock,
        "claim": "Stub factory. fixture receipt only. No H3 or Qwen process ran.",
    }
    data = {
        "still_vs_lock": still_vs_lock,
        "ng_reason": ng_reason,
        "notes": "test receipt",
    }
    if watched:
        data["watched"] = "true"
    response = client.post(
        f"/api/episodes/{episode_id}/shots/{shot_id}/preview",
        headers=auth,
        data=data,
        files={"file": ("hop1.json", json.dumps(payload).encode("utf-8"), "application/json")},
    )
    assert response.status_code in {200, 201}, response.text
    return response.json()


def sign_off(client, auth, episode_id: str, note: str = "reviewer sign-off") -> dict:
    response = client.post(
        f"/api/episodes/{episode_id}/review/signoff",
        headers=auth,
        json={"note": note},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["signed_off"] is True
    return body


def wait_job(client, auth, job_id: str, timeout: float = 8.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}", headers=auth)
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] in {"succeeded", "failed", "cancelled"}:
            return last
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish: {last}")
