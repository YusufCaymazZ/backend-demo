# API Testing Guide

This guide provides complete test scenarios for the Backend Platform v3.0 API.

## Quick Test Sequence

### 1. Start the Application
```bash
docker compose up -d
```

### 2. Verify Health
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "3.0",
  "environment": "development",
  "timestamp": "2025-11-12T10:30:00.000000+00:00",
  "database": {
    "status": "connected",
    "type": "sqlite",
    "tables": "accessible"
  },
  "checks": {
    "users": 0,
    "events": 0
  }
}
```

---

## Complete Test Flow

### Step 1: Login (Get JWT Token)

**Bash/Linux/Mac:**
```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"userId":"test_player_001"}'
```

**PowerShell:**
```powershell
$response = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/login" `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"userId":"test_player_001"}'
$TOKEN = $response.token
echo "Token: $TOKEN"
```

**Expected Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "userId": "test_player_001"
}
```

**Save the token for subsequent requests!**

---

### Step 2: Earn Currency

**Bash (save token from previous step):**
```bash
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0X3BsYXllcl8wMDEiLCJleHAiOjE3NjI5Nzg5MzV9._Ohue7UasHWqKHpF1onZwTxPabNCt73nmZd1k_I0k5c"

curl -X POST http://localhost:8000/earn \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount":500,"reason":"daily_login_bonus"}'
```

**PowerShell:**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/earn" `
  -Headers @{
    "Authorization"="Bearer $TOKEN"
    "Content-Type"="application/json"
  } `
  -Body '{"amount":500,"reason":"daily_login_bonus"}'
```

**Expected Response:**
```json
{
  "ok": true,
  "balance": 500
}
```

**Test with different amounts:**
```bash
# Earn 1000 for completing a quest
curl -X POST http://localhost:8000/earn \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount":1000,"reason":"quest_complete"}'

# Earn 250 for daily streak
curl -X POST http://localhost:8000/earn \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount":250,"reason":"daily_streak_bonus"}'
```

---

### Step 3: Check Balance

**Bash:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/balance
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/balance" `
  -Headers @{"Authorization"="Bearer $TOKEN"}
```

**Expected Response:**
```json
{
  "userId": "test_player_001",
  "balance": 1750
}
```

---

### Step 4: Track Events

**Event without timestamp (uses current time):**
```bash
curl -X POST http://localhost:8000/event \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "eventType":"level_complete",
    "meta":"{\"level\":1,\"score\":1500,\"time_seconds\":120}"
  }'
```

**Event with specific timestamp:**
```bash
curl -X POST http://localhost:8000/event \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "eventType":"level_complete",
    "meta":"{\"level\":2,\"score\":2500,\"time_seconds\":95}",
    "timestampUtc":"2025-11-12T10:30:00Z"
  }'
```

**PowerShell:**
```powershell
$body = @{
  eventType = "level_complete"
  meta = '{"level":3,"score":3500,"time_seconds":80}'
} | ConvertTo-Json

Invoke-RestMethod -Method POST -Uri "http://localhost:8000/event" `
  -Headers @{
    "Authorization"="Bearer $TOKEN"
    "Content-Type"="application/json"
  } `
  -Body $body
```

**Expected Response:**
```json
{
  "ok": true,
  "eventId": 1
}
```

**Track various event types:**
```bash
# Purchase event
curl -X POST http://localhost:8000/event \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "eventType":"purchase",
    "meta":"{\"item_id\":\"sword_legendary\",\"price\":500,\"currency\":\"gems\"}"
  }'

# Boss defeat
curl -X POST http://localhost:8000/event \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "eventType":"boss_defeat",
    "meta":"{\"boss_name\":\"dragon\",\"attempts\":3,\"party_size\":4}"
  }'

# Session start
curl -X POST http://localhost:8000/event \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "eventType":"session_start",
    "meta":"{\"device\":\"iOS\",\"version\":\"1.2.3\"}"
  }'
```

---

### Step 5: Get Event History

**Get all events:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/events?limit=100&offset=0"
```

**Filter by event type:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/events?event_type=level_complete&limit=50"
```

**Filter by time range:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/events?start_time=2025-11-12T00:00:00Z&end_time=2025-11-12T23:59:59Z"
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/events?limit=100" `
  -Headers @{"Authorization"="Bearer $TOKEN"}
```

**Expected Response:**
```json
{
  "events": [
    {
      "id": 3,
      "type": "session_start",
      "ts": "2025-11-12T10:45:00.000000+00:00",
      "meta": "{\"device\":\"iOS\",\"version\":\"1.2.3\"}"
    },
    {
      "id": 2,
      "type": "boss_defeat",
      "ts": "2025-11-12T10:40:00.000000+00:00",
      "meta": "{\"boss_name\":\"dragon\",\"attempts\":3}"
    },
    {
      "id": 1,
      "type": "level_complete",
      "ts": "2025-11-12T10:30:00.000000+00:00",
      "meta": "{\"level\":1,\"score\":1500}"
    }
  ],
  "total": 3,
  "limit": 100,
  "offset": 0,
  "hasMore": false
}
```

---

### Step 6: Get Statistics

**Global stats (all users):**
```bash
curl http://localhost:8000/stats?limit=100
```

**User-specific stats (requires authentication):**
```bash
curl "http://localhost:8000/stats?uid=test_player_001&limit=50"
```

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/stats?limit=100"
```

**Expected Response:**
```json
{
  "stats": [
    {
      "eventType": "level_complete",
      "count": 3
    },
    {
      "eventType": "earn",
      "count": 3
    },
    {
      "eventType": "purchase",
      "count": 1
    },
    {
      "eventType": "boss_defeat",
      "count": 1
    }
  ],
  "total": 4,
  "limit": 100,
  "offset": 0,
  "hasMore": false
}
```

---

### Step 7: Run Data Pipeline

```bash
curl -X POST http://localhost:8000/run-pipeline
```

**PowerShell:**
```powershell
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/run-pipeline"
```

**Expected Response:**
```json
{
  "ok": true,
  "returncode": 0,
  "stdout": "Starting data processing pipeline...\n✓ Loaded purchases_raw.csv (500 rows)\n✓ Loaded confirmed_purchases.csv (450 rows)\n✓ Purchase reconciliation complete...\n✓ ROAS calculation complete...\n✓ ARPDAU calculation complete...\nPipeline execution completed successfully!",
  "stderr": ""
}
```

---

### Step 8: View Generated Reports

The pipeline generates several reports in the `reports/` directory:

```bash
# View reconciliation report
cat reports/reconciliation.json

# View ROAS (Return on Ad Spend) report
cat reports/roas_d1.json

# View ROAS anomalies
cat reports/roas_anomaly.json

# View ARPDAU (Average Revenue Per Daily Active User)
cat reports/arpdau_d1.json

# View curated purchases
head -20 reports/purchases_curated.csv
```

**PowerShell:**
```powershell
Get-Content reports\reconciliation.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
Get-Content reports\roas_d1.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
Get-Content reports\arpdau_d1.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

---

## Advanced Features

### Idempotency Testing

Idempotency keys prevent duplicate operations:

```bash
# First request with idempotency key
curl -X POST http://localhost:8000/earn \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: unique-key-12345" \
  -d '{"amount":100,"reason":"test"}'

# Duplicate request with same key - returns cached response
curl -X POST http://localhost:8000/earn \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: unique-key-12345" \
  -d '{"amount":100,"reason":"test"}'
```

The second request will return the same response without adding currency again.

---

### Deeplink Tracking

Track attribution from marketing campaigns:

```bash
curl "http://localhost:8000/track?character=warrior&campaign=summer_promo"
```

**Expected Response:**
```json
{
  "ok": true,
  "logged": {
    "character": "warrior",
    "campaign": "summer_promo"
  }
}
```

---

## Error Scenarios

### 401 Unauthorized (Invalid/Expired Token)
```bash
curl -H "Authorization: Bearer invalid_token" \
  http://localhost:8000/balance
```

**Response:**
```json
{
  "detail": "invalid_token"
}
```

### 400 Bad Request (Invalid Data)
```bash
curl -X POST http://localhost:8000/earn \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount":-100}'
```

**Response:**
```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["body", "amount"],
      "msg": "Input should be greater than or equal to 1"
    }
  ]
}
```

### 404 Not Found (User Doesn't Exist)
```bash
# Login as different user
TOKEN2=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"userId":"nonexistent_user"}' | jq -r .token)

# Try to get balance before any earn operations
curl -H "Authorization: Bearer $TOKEN2" \
  http://localhost:8000/balance
```

---

## Complete Test Script

Save this as `test_api.sh` (Linux/Mac) or `test_api.ps1` (Windows):

**Bash:**
```bash
#!/bin/bash

BASE_URL="http://localhost:8000"

echo "=== Testing Backend API v3.0 ==="

# 1. Health check
echo -e "\n1. Health Check"
curl -s $BASE_URL/health | jq

# 2. Login
echo -e "\n2. Login"
TOKEN=$(curl -s -X POST $BASE_URL/login \
  -H "Content-Type: application/json" \
  -d '{"userId":"test_user"}' | jq -r .token)
echo "Token: ${TOKEN:0:50}..."

# 3. Earn currency
echo -e "\n3. Earn Currency (500)"
curl -s -X POST $BASE_URL/earn \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount":500,"reason":"test"}' | jq

# 4. Check balance
echo -e "\n4. Check Balance"
curl -s -H "Authorization: Bearer $TOKEN" \
  $BASE_URL/balance | jq

# 5. Track event
echo -e "\n5. Track Event"
curl -s -X POST $BASE_URL/event \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"eventType":"test_event","meta":"{\"foo\":\"bar\"}"}' | jq

# 6. Get events
echo -e "\n6. Get Events"
curl -s -H "Authorization: Bearer $TOKEN" \
  "$BASE_URL/events?limit=10" | jq

# 7. Run pipeline
echo -e "\n7. Run Pipeline"
curl -s -X POST $BASE_URL/run-pipeline | jq

echo -e "\n=== All tests complete ==="
```

**PowerShell:**
```powershell
$BASE_URL = "http://localhost:8000"

Write-Host "=== Testing Backend API v3.0 ===" -ForegroundColor Green

# 1. Health check
Write-Host "`n1. Health Check" -ForegroundColor Yellow
Invoke-RestMethod -Uri "$BASE_URL/health" | ConvertTo-Json -Depth 10

# 2. Login
Write-Host "`n2. Login" -ForegroundColor Yellow
$response = Invoke-RestMethod -Method POST -Uri "$BASE_URL/login" `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"userId":"test_user"}'
$TOKEN = $response.token
Write-Host "Token: $($TOKEN.Substring(0, [Math]::Min(50, $TOKEN.Length)))..."

# 3. Earn currency
Write-Host "`n3. Earn Currency (500)" -ForegroundColor Yellow
Invoke-RestMethod -Method POST -Uri "$BASE_URL/earn" `
  -Headers @{
    "Authorization"="Bearer $TOKEN"
    "Content-Type"="application/json"
  } `
  -Body '{"amount":500,"reason":"test"}' | ConvertTo-Json

# 4. Check balance
Write-Host "`n4. Check Balance" -ForegroundColor Yellow
Invoke-RestMethod -Uri "$BASE_URL/balance" `
  -Headers @{"Authorization"="Bearer $TOKEN"} | ConvertTo-Json

# 5. Track event
Write-Host "`n5. Track Event" -ForegroundColor Yellow
Invoke-RestMethod -Method POST -Uri "$BASE_URL/event" `
  -Headers @{
    "Authorization"="Bearer $TOKEN"
    "Content-Type"="application/json"
  } `
  -Body '{"eventType":"test_event","meta":"{\"foo\":\"bar\"}"}' | ConvertTo-Json

# 6. Get events
Write-Host "`n6. Get Events" -ForegroundColor Yellow
Invoke-RestMethod -Uri "$BASE_URL/events?limit=10" `
  -Headers @{"Authorization"="Bearer $TOKEN"} | ConvertTo-Json -Depth 10

# 7. Run pipeline
Write-Host "`n7. Run Pipeline" -ForegroundColor Yellow
Invoke-RestMethod -Method POST -Uri "$BASE_URL/run-pipeline" | ConvertTo-Json

Write-Host "`n=== All tests complete ===" -ForegroundColor Green
```

---

## Postman Collection

Import `postman_collection.json` (see separate file) for a complete interactive test suite.

---

## Interactive API Documentation

The easiest way to test the API is through Swagger UI:

1. Start the application: `docker compose up -d`
2. Open browser: http://localhost:8000/docs
3. Click **POST /login** → Try it out → Execute
4. Copy the token from the response
5. Click **Authorize** button (lock icon at top-right)
6. Paste the token → Authorize → Close
7. Now test any endpoint with automatic authentication!

Alternative documentation: http://localhost:8000/redoc

---

## Report Samples

After running `/run-pipeline`, you'll find these reports in the `reports/` directory:

**reconciliation.json** - Purchase matching statistics:
```json
{
  "total_appsflyer": 500,
  "total_confirmed": 450,
  "matched": 445,
  "match_rate": 0.989,
  "unmatched_af": 55,
  "unmatched_confirmed": 5
}
```

**roas_d1.json** - Return on Ad Spend per campaign:
```json
{
  "campaign_summer": {
    "revenue": 15420.50,
    "cost": 5000.00,
    "roas": 3.08,
    "installs": 1250
  },
  "campaign_winter": {
    "revenue": 8930.25,
    "cost": 3500.00,
    "roas": 2.55,
    "installs": 890
  }
}
```

**roas_anomaly.json** - Campaigns with performance issues:
```json
{
  "anomalies": [
    {
      "campaign": "campaign_test",
      "roas": 0.42,
      "threshold": 1.0,
      "revenue": 420.00,
      "cost": 1000.00,
      "severity": "high"
    }
  ]
}
```

**arpdau_d1.json** - Average Revenue Per Daily Active User:
```json
{
  "campaign_summer": {
    "revenue": 15420.50,
    "dau": 1150,
    "arpdau": 13.41
  },
  "campaign_winter": {
    "revenue": 8930.25,
    "dau": 820,
    "arpdau": 10.89
  }
}
```

---

## Verification Checklist

Use this checklist to verify your deployment:

- [ ] `docker compose up -d` starts successfully
- [ ] `/health` returns status "healthy"
- [ ] `/login` returns a JWT token
- [ ] `/earn` increases balance (check with `/balance`)
- [ ] `/event` creates events (verify with `/events`)
- [ ] `/run-pipeline` executes without errors
- [ ] `reports/` directory contains 5 output files
- [ ] All report files have valid JSON/CSV content
- [ ] Swagger UI is accessible at `/docs`
- [ ] Authentication works in Swagger UI

---

## Next Steps

1. Test the API using this guide
2. Review generated reports in `reports/` directory
3. Explore the interactive Swagger UI at http://localhost:8000/docs
4. Read [PROJECT_BRIEF.md](PROJECT_BRIEF.md) for technical architecture details
5. Check [README.md](README.md) for deployment and configuration

---

**For questions or issues, refer to the Troubleshooting section in README.md**
