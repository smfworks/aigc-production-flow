from tests.helpers import green_ready_episode


def test_edl_and_playlist_from_edit_list(client, auth):
    _, episode, shots = green_ready_episode(client, auth, "EDL")
    episode_id = episode["id"]

    edl = client.get(f"/api/episodes/{episode_id}/export/edl", headers=auth)
    assert edl.status_code == 200, edl.text
    text = edl.text
    assert "TITLE:" in text
    assert "FCM: NON-DROP FRAME" in text
    assert "FROM CLIP NAME:" in text
    assert "00:00:00:00" in text
    assert "Not an NLE" in text

    xml = client.get(f"/api/episodes/{episode_id}/export/fcpxml", headers=auth)
    assert xml.status_code == 200
    assert "<xmeml" in xml.text
    assert "<clipitem>" in xml.text

    playlist = client.get(f"/api/episodes/{episode_id}/export/playlist", headers=auth)
    assert playlist.status_code == 200
    body = playlist.json()
    assert body["format"] == "aigc-shot-playlist"
    assert body["fps"] == 24
    assert len(body["shots"]) == len(shots)
    assert body["shots"][0]["media_path"] is None
    assert body["shots"][0]["join"] == "fadeblack"
    assert "Metadata-only" in body["note"]

    hop = client.post(
        "/api/jobs",
        headers=auth,
        json={"episode_id": episode_id, "shot_id": shots[0]["id"], "job_type": "clip-hop1"},
    )
    assert hop.status_code == 201, hop.text
    with_media = client.get(f"/api/episodes/{episode_id}/export/playlist", headers=auth).json()
    assert with_media["shots"][0]["media_path"]
    edl_media = client.get(f"/api/episodes/{episode_id}/export/edl", headers=auth).text
    assert "SOURCE FILE:" in edl_media
    assert "no preview receipt yet" not in edl_media.split("SOURCE FILE:")[1].splitlines()[0]
