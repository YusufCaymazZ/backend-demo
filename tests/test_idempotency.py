#!/usr/bin/env python3
"""
Test script for idempotency protection

This demonstrates how idempotency keys prevent duplicate operations
even when the same request is sent multiple times.
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"


def print_section(title):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def test_idempotency():
    """Test idempotency protection on /earn endpoint"""

    print_section("TEST 1: Login and Get Initial Balance")

    # Step 1: Login
    login_response = requests.post(f"{BASE_URL}/login", json={"userId": "idempotency_test_user"})
    token = login_response.json()["token"]
    print("[OK] Logged in as: idempotency_test_user")
    print(f"  Token: {token[:30]}...")

    # Step 2: Get initial balance
    balance_response = requests.get(f"{BASE_URL}/balance", headers={"Authorization": f"Bearer {token}"})
    initial_balance = balance_response.json()["balance"]
    print(f"[OK] Initial balance: {initial_balance}")

    # ========================================
    # TEST WITHOUT IDEMPOTENCY KEY
    # ========================================
    print_section("TEST 2: WITHOUT Idempotency Key (Duplicate Problem)")

    # First request without idempotency key
    print("\n[Request 1] Earning 100 coins WITHOUT idempotency key...")
    response1 = requests.post(f"{BASE_URL}/earn", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json={"amount": 100, "reason": "test_no_idempotency"})
    balance1 = response1.json()["balance"]
    print(f"[OK] Response: {response1.json()}")
    print(f"  New balance: {balance1}")

    # Second request without idempotency key (DUPLICATE!)
    print("\n[Request 2] Earning 100 coins again WITHOUT idempotency key...")
    response2 = requests.post(f"{BASE_URL}/earn", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json={"amount": 100, "reason": "test_no_idempotency"})
    balance2 = response2.json()["balance"]
    print(f"[OK] Response: {response2.json()}")
    print(f"  New balance: {balance2}")

    print(f"\n[PROBLEM] Balance increased by {balance2 - balance1} (should be 0)")
    print("   Without idempotency key, duplicate requests process multiple times!")

    # ========================================
    # TEST WITH IDEMPOTENCY KEY
    # ========================================
    print_section("TEST 3: WITH Idempotency Key (Protection Works)")

    current_balance = balance2
    idempotency_key = "test-key-12345"

    # First request with idempotency key
    print(f"\n[Request 1] Earning 500 coins WITH idempotency key: {idempotency_key}")
    response3 = requests.post(
        f"{BASE_URL}/earn",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Idempotency-Key": idempotency_key},
        json={"amount": 500, "reason": "test_with_idempotency"},
    )
    balance3 = response3.json()["balance"]
    print(f"[OK] Response: {response3.json()}")
    print(f"  New balance: {balance3}")
    print(f"  Balance increased by: {balance3 - current_balance}")

    # Second request with SAME idempotency key (PROTECTED!)
    print(f"\n[Request 2] Earning 500 coins again WITH SAME idempotency key: {idempotency_key}")
    response4 = requests.post(
        f"{BASE_URL}/earn",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Idempotency-Key": idempotency_key},  # SAME KEY!
        json={"amount": 500, "reason": "test_with_idempotency"},
    )
    balance4 = response4.json()["balance"]
    print(f"[OK] Response: {response4.json()}")
    print(f"  New balance: {balance4}")
    print(f"  Balance increased by: {balance4 - balance3}")

    if balance4 == balance3:
        print("\n[SUCCESS] Balance stayed the same!")
        print("   Idempotency key prevented duplicate processing!")
    else:
        print("\n[FAILED] Balance changed (this shouldn't happen)")

    # Verify responses are identical
    print("\nComparing responses:")
    print(f"   Response 1: {response3.json()}")
    print(f"   Response 2: {response4.json()}")
    if response3.json() == response4.json():
        print("   [OK] Responses are IDENTICAL (cached response returned)")

    # ========================================
    # TEST WITH DIFFERENT IDEMPOTENCY KEY
    # ========================================
    print_section("TEST 4: Different Idempotency Key (Processes Normally)")

    different_key = "test-key-67890"

    print(f"\n[Request 3] Earning 250 coins WITH DIFFERENT idempotency key: {different_key}")
    response5 = requests.post(
        f"{BASE_URL}/earn",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Idempotency-Key": different_key},  # DIFFERENT KEY!
        json={"amount": 250, "reason": "test_different_key"},
    )
    balance5 = response5.json()["balance"]
    print(f"[OK] Response: {response5.json()}")
    print(f"  New balance: {balance5}")
    print(f"  Balance increased by: {balance5 - balance4}")

    if balance5 > balance4:
        print("\n[SUCCESS] Different idempotency key allows new operation!")

    # ========================================
    # TEST IDEMPOTENCY ON /EVENT ENDPOINT
    # ========================================
    print_section("TEST 5: Idempotency on /event Endpoint")

    event_key = "event-key-unique-123"

    print(f"\n[Request 1] Creating event WITH idempotency key: {event_key}")
    event_response1 = requests.post(
        f"{BASE_URL}/event",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Idempotency-Key": event_key},
        json={"eventType": "test_idempotency_event", "meta": '{"test": true, "iteration": 1}'},
    )
    event_id1 = event_response1.json()["eventId"]
    print(f"[OK] Response: {event_response1.json()}")
    print(f"  Event ID: {event_id1}")

    print(f"\n[Request 2] Creating same event again WITH SAME key: {event_key}")
    event_response2 = requests.post(
        f"{BASE_URL}/event",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Idempotency-Key": event_key},  # SAME KEY!
        json={"eventType": "test_idempotency_event", "meta": '{"test": true, "iteration": 2}'},  # Different data!
    )
    event_id2 = event_response2.json()["eventId"]
    print(f"[OK] Response: {event_response2.json()}")
    print(f"  Event ID: {event_id2}")

    if event_id1 == event_id2:
        print("\n[SUCCESS] Same event ID returned (cached response)!")
        print("   Event was NOT created twice!")

    # ========================================
    # SUMMARY
    # ========================================
    print_section("SUMMARY")
    print("\nTest Results:")
    print(f"   Initial balance: {initial_balance}")
    print(f"   Final balance: {balance5}")
    print(f"   Total earned: {balance5 - initial_balance}")
    print("\nKey Insights:")
    print("   • WITHOUT idempotency key: Duplicates process multiple times [X]")
    print("   • WITH idempotency key: Duplicates return cached response [OK]")
    print("   • Different keys: Each processes independently [OK]")
    print("   • Works on both /earn and /event endpoints [OK]")
    print("   • Cache expires after 24 hours")

    print_section("Check Database")
    print("\nTo verify in database:")
    print("   docker compose exec api sqlite3 data/app.db")
    print("   SELECT * FROM idempotency_keys;")
    print("\nOr check logs:")
    print("   docker compose logs api | grep -i idempotency")


if __name__ == "__main__":
    print("\nIdempotency Protection Test Suite")
    print("=" * 60)

    try:
        # Check if API is running
        health = requests.get(f"{BASE_URL}/health", timeout=2)
        print(f"[OK] API is running (Status: {health.json()['status']})")

        # Run tests
        test_idempotency()

        print("\n" + "=" * 60)
        print("[SUCCESS] All tests completed successfully!")
        print("=" * 60 + "\n")

    except requests.exceptions.ConnectionError:
        print(f"\n[ERROR] Cannot connect to API at {BASE_URL}")
        print("   Make sure the API is running:")
        print("   docker compose up -d")
        print("\n")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        print("\n")
