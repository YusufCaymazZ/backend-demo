#!/usr/bin/env python3
"""
Test script for AppsFlyer postback endpoint with HMAC signature
"""
import hmac
import hashlib
import json
import requests
import sys

# Configuration
API_URL = "http://localhost:8000/af/postback"
AF_SECRET = "appsflyer_secret_key"  # Must match AF_SECRET in your .env file

# Test payload (sample AppsFlyer postback data)
payload = {
    "event_name": "af_purchase",
    "appsflyer_id": "1234567890-abcdef",
    "customer_user_id": "player_test_001",
    "event_revenue_usd": "9.99",
    "event_time": "2025-11-12 18:00:00",
    "campaign": "summer_campaign",
    "media_source": "google_ads",
    "af_revenue": "9.99",
    "af_currency": "USD",
}


def generate_signature(payload_dict: dict, secret: str) -> str:
    """
    Generate HMAC-SHA256 signature for AppsFlyer postback
    """
    # Convert payload to JSON string (same format AppsFlyer sends)
    payload_str = json.dumps(payload_dict, separators=(',', ':'), sort_keys=False)

    # Create HMAC signature
    signature = hmac.new(secret.encode('utf-8'), payload_str.encode('utf-8'), hashlib.sha256).hexdigest()

    return signature, payload_str


def test_without_signature():
    """Test 1: Send postback WITHOUT signature (should work but warn)"""
    print("=" * 60)
    print("TEST 1: Postback WITHOUT signature")
    print("=" * 60)

    try:
        response = requests.post(API_URL, json=payload, headers={"Content-Type": "application/json"})

        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")

        if response.status_code == 200:
            print("[SUCCESS] Postback accepted (but check logs for warning)")
        else:
            print("[FAILED] Unexpected status code")

    except Exception as e:
        print(f"[ERROR] {e}")

    print()


def test_with_signature():
    """Test 2: Send postback WITH valid signature (production-ready)"""
    print("=" * 60)
    print("TEST 2: Postback WITH valid signature")
    print("=" * 60)

    # Generate signature
    signature, payload_str = generate_signature(payload, AF_SECRET)

    print(f"Payload: {payload_str}")
    print(f"Signature: {signature}")
    print()

    try:
        response = requests.post(API_URL, data=payload_str, headers={"Content-Type": "application/json", "X-AF-Signature": signature})  # Send as raw string (not json=payload)

        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")

        if response.status_code == 200:
            print("[SUCCESS] Postback accepted with valid signature")
        else:
            print("[FAILED] Signature verification failed or other error")

    except Exception as e:
        print(f"[ERROR] {e}")

    print()


def test_with_invalid_signature():
    """Test 3: Send postback WITH invalid signature (should reject)"""
    print("=" * 60)
    print("TEST 3: Postback WITH invalid signature (should fail)")
    print("=" * 60)

    payload_str = json.dumps(payload)
    fake_signature = "fake_invalid_signature_12345"

    print(f"Payload: {payload_str}")
    print(f"Fake Signature: {fake_signature}")
    print()

    try:
        response = requests.post(API_URL, data=payload_str, headers={"Content-Type": "application/json", "X-AF-Signature": fake_signature})

        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")

        if response.status_code == 401:
            print("[SUCCESS] Invalid signature correctly rejected")
        else:
            print("[WARNING] Invalid signature should return 401")

    except Exception as e:
        print(f"[ERROR] {e}")

    print()


def test_modified_payload():
    """Test 4: Send tampered payload (signature won't match)"""
    print("=" * 60)
    print("TEST 4: Tampered payload (signature won't match)")
    print("=" * 60)

    # Generate signature for original payload
    signature, _ = generate_signature(payload, AF_SECRET)

    # Modify the payload after signing (simulate tampering)
    tampered_payload = payload.copy()
    tampered_payload["event_revenue_usd"] = "999.99"  # Changed!
    tampered_str = json.dumps(tampered_payload)

    print(f"Original Payload Revenue: {payload['event_revenue_usd']}")
    print(f"Tampered Payload Revenue: {tampered_payload['event_revenue_usd']}")
    print("Using signature from ORIGINAL payload")
    print()

    try:
        response = requests.post(API_URL, data=tampered_str, headers={"Content-Type": "application/json", "X-AF-Signature": signature})  # Signature won't match tampered data

        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")

        if response.status_code == 401:
            print("[SUCCESS] Tampered data correctly rejected")
        else:
            print("[WARNING] Tampered data should be rejected")

    except Exception as e:
        print(f"[ERROR] {e}")

    print()


def generate_curl_command():
    """Generate a curl command for manual testing"""
    print("=" * 60)
    print("CURL COMMAND for manual testing")
    print("=" * 60)

    signature, payload_str = generate_signature(payload, AF_SECRET)

    curl_cmd = """curl -X POST http://localhost:8000/af/postback \\
  -H "Content-Type: application/json" \\
  -H "X-AF-Signature: {signature}" \\
  -d '{payload_str}'
"""

    print(curl_cmd)
    print()


if __name__ == "__main__":
    print("\nAppsFlyer Postback Testing Suite\n")

    # Check if API is running
    try:
        health_check = requests.get("http://localhost:8000/health", timeout=2)
        print(f"API is running (Status: {health_check.json()['status']})\n")
    except Exception as e:
        print("ERROR: Cannot connect to API. Is it running?")
        print("   Run: docker compose up -d")
        print(f"   Error: {e}\n")
        sys.exit(1)

    # Run all tests
    test_without_signature()
    test_with_signature()
    test_with_invalid_signature()
    test_modified_payload()
    generate_curl_command()

    print("=" * 60)
    print("All tests complete! Check logs with:")
    print("docker compose logs -f api | grep -i appsflyer")
    print("=" * 60)
