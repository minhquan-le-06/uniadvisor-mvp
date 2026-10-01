"""HTTP API on the tiny simulated world."""

import pytest


@pytest.fixture
def client(use_tiny):
    from fastapi.testclient import TestClient

    from uniadvisor.api import app

    return TestClient(app)


def test_health_and_programs(client):
    h = client.get("/health").json()
    assert (h["programs"], h["schools"], h["database_kind"]) == (12, 3, "simulated")
    progs = client.get("/programs", params={"city": "Hà Nội"}).json()
    assert len(progs) == 8 and all(p["program_id"].startswith("SIM-HN") for p in progs)
    one = client.get("/programs/SIM-HN1:IT").json()
    assert one["history"]["2026"] == 25.5 and one["tuition_provenance"] == "simulated"
    assert client.get("/programs/NOPE").status_code == 404


def test_advise(client):
    r = client.post("/advise", json={"scores": {"TO": 8.4, "VA": 7.0, "LI": 8.0, "N1": 8.2}, "free_text": "Em muốn học kinh tế ở Hà Nội"})
    assert r.status_code == 200
    body = r.json()
    assert body["list"] and all(0 <= p["p_admit"] <= 1 and p["bucket"] != "unlikely" for p in body["list"])
    assert all(p["tuition_provenance"] in ("simulated", "estimated", "missing") for p in body["list"] + body["alternatives"])


@pytest.mark.parametrize("scores", [{"TO": 11}, {"TO": -1}, {}])
def test_advise_rejects_bad_scores(client, scores):
    assert client.post("/advise", json={"scores": scores}).status_code == 422
