"""HTTP API smoke test on the real processed data (skipped when data/processed is missing)."""

import pytest

from uniadvisor.paths import PROCESSED

pytestmark = pytest.mark.skipif(not (PROCESSED / "programs.csv").exists(), reason="run `uniadvisor build` first")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from uniadvisor.api import app

    return TestClient(app)


def test_health_and_programs(client):
    h = client.get("/health").json()
    assert h["programs"] > 0 and h["schools"] > 0
    progs = client.get("/programs", params={"limit": 2}).json()
    assert 0 < len(progs) <= 2
    assert client.get(f"/programs/{progs[0]['program_id']}").status_code == 200
    assert client.get("/programs/NOPE").status_code == 404


def test_advise(client):
    r = client.post("/advise", json={"scores": {"TO": 8.4, "VA": 7.0, "LI": 8.0, "N1": 8.2}, "free_text": "Em muốn học CNTT ở Hà Nội"})
    assert r.status_code == 200
    body = r.json()
    assert body["list"] and all(0 <= p["p_admit"] <= 1 and p["bucket"] != "unlikely" for p in body["list"])


@pytest.mark.parametrize("scores", [{"TO": 11}, {"TO": -1}, {}])
def test_advise_rejects_bad_scores(client, scores):
    assert client.post("/advise", json={"scores": scores}).status_code == 422
