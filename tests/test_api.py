from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    # Verify enhanced health response structure
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "environment" in data
    assert data["database"]["status"] == "connected"
    assert "checks" in data


def test_login():
    response = client.post("/login", json={"userId": "test_user"})
    assert response.status_code == 200
    assert "token" in response.json()
    assert response.json()["userId"] == "test_user"


def test_earn_without_auth():
    response = client.post("/earn", json={"amount": 50, "reason": "test"})
    # HTTPBearer returns 403 Forbidden when auth is missing
    assert response.status_code == 403


def test_earn_with_auth():
    # First login
    login_response = client.post("/login", json={"userId": "test_user"})
    token = login_response.json()["token"]

    # Then try to earn
    response = client.post("/earn", json={"amount": 50, "reason": "test"}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["ok"] == True
    assert response.json()["balance"] >= 50  # Balance should be at least the earned amount


def test_balance():
    # First login
    login_response = client.post("/login", json={"userId": "test_user"})
    token = login_response.json()["token"]

    # Check balance
    response = client.get("/balance", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "balance" in response.json()


def test_event():
    # First login
    login_response = client.post("/login", json={"userId": "test_user"})
    token = login_response.json()["token"]

    # Post event
    response = client.post("/event", json={"eventType": "test_event", "meta": "test"}, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["ok"] == True
    assert "eventId" in response.json()


def test_events_list():
    # First login
    login_response = client.post("/login", json={"userId": "test_user"})
    token = login_response.json()["token"]

    # Post some events
    client.post("/event", json={"eventType": "test_event1", "meta": "test1"}, headers={"Authorization": f"Bearer {token}"})
    client.post("/event", json={"eventType": "test_event2", "meta": "test2"}, headers={"Authorization": f"Bearer {token}"})

    # Get events list
    response = client.get("/events", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert len(events) > 0
    assert all(isinstance(e["id"], int) for e in events)


def test_stats():
    response = client.get("/stats")
    assert response.status_code == 200
    stats = response.json()
    assert isinstance(stats, list)
    assert all("eventType" in stat and "count" in stat for stat in stats)


def test_track():
    response = client.get("/track", params={"character": "45", "campaign": "Campaign_A"})
    assert response.status_code == 200
    assert response.json()["ok"] == True
    assert response.json()["logged"]["character"] == "45"
    assert response.json()["logged"]["campaign"] == "Campaign_A"
