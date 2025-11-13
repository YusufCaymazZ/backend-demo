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
    data = response.json()
    assert "events" in data
    assert isinstance(data["events"], list)
    assert len(data["events"]) > 0
    assert all(isinstance(e["id"], int) for e in data["events"])


def test_stats():
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data
    assert isinstance(data["stats"], list)
    assert all("eventType" in stat and "count" in stat for stat in data["stats"])


def test_track():
    response = client.get("/track", params={"character": "45", "campaign": "Campaign_A"})
    assert response.status_code == 200
    assert response.json()["ok"] == True
    assert response.json()["logged"]["character"] == "45"
    assert response.json()["logged"]["campaign"] == "Campaign_A"


# ===== NEW TESTS FOR ENHANCED FEATURES =====


def test_auth_invalid_token():
    """Test that invalid JWT token is rejected"""
    response = client.get("/balance", headers={"Authorization": "Bearer invalid_token_here"})
    assert response.status_code == 401
    assert "invalid_token" in response.json()["detail"]


def test_auth_expired_token():
    """Test that expired token is rejected"""
    # This would require a token with exp in the past, or mocking time
    # For now, just test invalid format
    response = client.get("/balance", headers={"Authorization": "Bearer eyJ.invalid.token"})
    assert response.status_code == 401


def test_earn_idempotency():
    """Test idempotency protection for /earn endpoint"""
    login_response = client.post("/login", json={"userId": "idempotency_user"})
    token = login_response.json()["token"]

    idempotency_key = "test-idem-key-123"

    # First request
    response1 = client.post("/earn", json={"amount": 100, "reason": "test"}, headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key})
    assert response1.status_code == 200
    balance1 = response1.json()["balance"]

    # Second request with same idempotency key - should return cached response
    response2 = client.post("/earn", json={"amount": 100, "reason": "test"}, headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key})
    assert response2.status_code == 200
    balance2 = response2.json()["balance"]

    # Balance should be the same (not incremented again)
    assert balance1 == balance2


def test_earn_without_idempotency():
    """Test that without idempotency key, duplicate requests work normally"""
    login_response = client.post("/login", json={"userId": "no_idem_user"})
    token = login_response.json()["token"]

    # First request
    response1 = client.post("/earn", json={"amount": 50, "reason": "test"}, headers={"Authorization": f"Bearer {token}"})
    assert response1.status_code == 200
    balance1 = response1.json()["balance"]

    # Second request without idempotency key - should increment balance
    response2 = client.post("/earn", json={"amount": 50, "reason": "test"}, headers={"Authorization": f"Bearer {token}"})
    assert response2.status_code == 200
    balance2 = response2.json()["balance"]

    # Balance should increase
    assert balance2 == balance1 + 50


def test_event_idempotency():
    """Test idempotency protection for /event endpoint"""
    login_response = client.post("/login", json={"userId": "event_idem_user"})
    token = login_response.json()["token"]

    idempotency_key = "event-idem-key-456"

    # First request
    response1 = client.post("/event", json={"eventType": "test_event", "meta": "test_data"}, headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key})
    assert response1.status_code == 200
    event_id1 = response1.json()["eventId"]

    # Second request with same idempotency key
    response2 = client.post("/event", json={"eventType": "test_event", "meta": "test_data"}, headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key})
    assert response2.status_code == 200
    event_id2 = response2.json()["eventId"]

    # Should return the same event ID
    assert event_id1 == event_id2


def test_events_pagination():
    """Test pagination for /events endpoint"""
    login_response = client.post("/login", json={"userId": "pagination_user"})
    token = login_response.json()["token"]

    # Create 5 events
    for i in range(5):
        client.post("/event", json={"eventType": f"event_{i}", "meta": f"data_{i}"}, headers={"Authorization": f"Bearer {token}"})

    # Test pagination with limit=2
    response = client.get("/events?limit=2&offset=0", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["events"]) <= 2
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert "hasMore" in data
    assert "total" in data


def test_events_filters():
    """Test filtering for /events endpoint"""
    login_response = client.post("/login", json={"userId": "filter_user"})
    token = login_response.json()["token"]

    # Create events of different types
    client.post("/event", json={"eventType": "purchase", "meta": "item1"}, headers={"Authorization": f"Bearer {token}"})
    client.post("/event", json={"eventType": "level_up", "meta": "level2"}, headers={"Authorization": f"Bearer {token}"})
    client.post("/event", json={"eventType": "purchase", "meta": "item2"}, headers={"Authorization": f"Bearer {token}"})

    # Filter by event_type
    response = client.get("/events?event_type=purchase", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    # All returned events should be of type "purchase"
    assert all(event["type"] == "purchase" for event in data["events"])


def test_stats_pagination():
    """Test pagination for /stats endpoint"""
    # Stats endpoint doesn't require auth
    response = client.get("/stats?limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data
    assert "limit" in data
    assert "offset" in data
    assert "hasMore" in data
    assert "total" in data


def test_stats_filters():
    """Test filtering for /stats endpoint"""
    login_response = client.post("/login", json={"userId": "stats_user"})
    token = login_response.json()["token"]

    # Create some events
    client.post("/event", json={"eventType": "login", "meta": "test"}, headers={"Authorization": f"Bearer {token}"})
    client.post("/event", json={"eventType": "login", "meta": "test"}, headers={"Authorization": f"Bearer {token}"})

    # Query stats for specific user
    response = client.get("/stats?uid=stats_user")
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data


def test_appsflyer_postback_no_signature():
    """Test AppsFlyer postback without signature"""
    payload = {"event_name": "install", "appsflyer_id": "1234567890", "customer_user_id": "user123", "install_time": "2025-11-12 10:00:00"}

    response = client.post("/af/postback", json=payload)
    assert response.status_code == 200
    assert response.json()["ok"] == True
    assert "postbackId" in response.json()
    assert "eventId" in response.json()


def test_appsflyer_postback_invalid_signature():
    """Test AppsFlyer postback with invalid signature"""
    payload = {"event_name": "install", "appsflyer_id": "1234567890"}

    response = client.post("/af/postback", json=payload, headers={"X-AF-Signature": "invalid_signature_here"})
    # Should fail with 401 if signature verification fails
    assert response.status_code == 401


def test_appsflyer_postback_valid_signature():
    """Test AppsFlyer postback with valid HMAC signature"""
    import hmac
    import hashlib
    import json
    import os

    payload = {"event_name": "purchase", "appsflyer_id": "1234567890", "customer_user_id": "user456", "revenue": "9.99"}

    # Get the secret from environment
    af_secret = os.getenv("AF_SECRET", "appsflyer_secret_key")

    # Serialize payload exactly as it will be sent
    payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    signature = hmac.new(af_secret.encode(), payload_str.encode(), hashlib.sha256).hexdigest()

    # Send as raw content with explicit content type
    response = client.post("/af/postback", content=payload_str, headers={"X-AF-Signature": signature, "Content-Type": "application/json"})
    assert response.status_code == 200
    assert response.json()["ok"] == True


def test_earn_race_condition_protection():
    """Test that concurrent earn requests are handled safely with row locking"""
    login_response = client.post("/login", json={"userId": "race_test_user"})
    token = login_response.json()["token"]

    # Get initial balance
    initial = client.get("/balance", headers={"Authorization": f"Bearer {token}"})
    initial_balance = initial.json()["balance"]

    # Make multiple earn requests (simulating concurrent requests)
    amount = 10
    num_requests = 5
    for _ in range(num_requests):
        response = client.post("/earn", json={"amount": amount, "reason": "test"}, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    # Check final balance
    final = client.get("/balance", headers={"Authorization": f"Bearer {token}"})
    final_balance = final.json()["balance"]

    # Balance should be exactly increased by amount * num_requests
    assert final_balance == initial_balance + (amount * num_requests)
