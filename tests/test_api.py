"""The test chat uses the same ledger as the library."""

from fastapi.testclient import TestClient

from commute_split.web import create_app


def test_http_demo_and_error_state(tmp_path):
    client = TestClient(create_app(tmp_path / "commute.db"))

    state = client.get("/api/state")
    assert state.status_code == 200
    body = state.json()
    assert body["messages"] == []
    assert body["nets"] == []
    assert [person["name"] for person in body["people"]][:4] == [
        "Adrian",
        "Alex",
        "Sam",
        "Riley",
    ]

    blank = client.post("/api/messages", json={"sender": "Adrian", "text": "   "})
    assert blank.status_code == 422 or blank.status_code == 400

    missing = client.post("/api/messages", json={"sender": "", "text": "I'm in."})
    assert missing.status_code == 422

    fare = client.post(
        "/api/messages",
        json={"sender": "Adrian", "text": "I paid $48, Alex and Sam rode."},
    )
    assert fare.status_code == 200
    nets = {
        (item["debtor"], item["creditor"]): item["cents"]
        for item in fare.json()["state"]["nets"]
    }
    assert nets == {("Alex", "Adrian"): 1600, ("Sam", "Adrian"): 1600}
    assert fare.json()["state"]["messages"][-1]["kind"] == "agent"

    payback = client.post(
        "/api/messages",
        json={"sender": "Alex", "text": "I just paid Adrian $16."},
    )
    assert payback.status_code == 200
    nets = {
        (item["debtor"], item["creditor"]): item["cents"]
        for item in payback.json()["state"]["nets"]
    }
    assert nets == {("Sam", "Adrian"): 1600}

    balance = client.post(
        "/api/messages",
        json={"sender": "Sam", "text": "What do I owe?"},
    )
    assert balance.status_code == 200
    assert balance.json()["reply"] == "You owe Adrian $16.00."
    assert balance.json()["changed_balances"] is False

    health = client.get("/api/health")
    assert health.json() == {"ok": True}

    page = client.get("/")
    assert page.status_code == 200
    assert "Fareline" in page.text
