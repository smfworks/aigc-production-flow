def test_healthz_is_public(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["live"] is True


def test_readyz_reports_db_and_worker(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["db"] is True
    assert body["job_worker"] == "inline"


def test_metrics_prometheus_text(client):
    client.get("/healthz")
    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    assert "studio_http_requests_total" in text
    assert "studio_job_queue_depth" in text
    assert "studio_adapter_health" in text
    assert "stub" in text
