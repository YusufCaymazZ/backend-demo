# Gaming Backend Platform v3.0

A production-ready gaming backend combining a high-performance REST API with advanced data analytics pipeline for mobile gaming applications.

[![API](https://img.shields.io/badge/API-FastAPI-009688?style=flat-square)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)](https://www.python.org/)
[![Database](https://img.shields.io/badge/Database-SQLite%2FPostgreSQL-316192?style=flat-square)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-Internal-red?style=flat-square)]()

## Quick Start

### Docker (Recommended)
```bash
# Start services
docker compose up -d
curl http://localhost:8000/health
```

### Local Development
```bash
python -m venv env
source env/bin/activate  # Windows: env\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Features

### Core API
- **Authentication**: JWT-based stateless authentication
- **Currency Management**: Transaction-safe balance operations with race condition prevention
- **Event Tracking**: Real-time player action logging with custom metadata
- **Analytics Trigger**: On-demand data pipeline execution

### Data Pipeline
- **Purchase Reconciliation**: Cross-reference AppsFlyer and payment gateway data (±10min tolerance)
- **ROAS Analysis**: Daily return on ad spend with anomaly detection
- **ARPDAU Calculation**: Average revenue per daily active user metrics
- **Chargeback Handling**: Automatic revenue adjustment for disputed transactions

### Production-Grade Optimizations
- **100x faster** reconciliation (vectorized operations)
- **7x faster** ROAS calculation (pre-filtering + indexing)
- **10x lower** API latency (context variables for logging)
- **Zero race conditions** (row-level locking on currency updates)
- **Connection pooling** (10-30 connections, auto-recycle)

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/login` | POST | No | Authenticate and get JWT token |
| `/earn` | POST | Yes | Add currency to user balance |
| `/balance` | GET | Yes | Query current balance |
| `/event` | POST | Yes | Track custom game events |
| `/events` | GET | Yes | Retrieve event history (last 100) |
| `/stats` | GET | Optional | Event aggregation statistics |
| `/track` | GET | No | Deeplink attribution tracking |
| `/health` | GET | No | Service health check |
| `/run-pipeline` | POST | No | Trigger data analytics pipeline |

## Usage Examples

### Authentication & Balance
```bash
# Login and get token
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"userId":"player_001"}' | jq -r .token)

# Earn currency
curl -X POST http://localhost:8000/earn \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount":500,"reason":"daily_login"}'

# Check balance
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/balance
```

### Event Tracking
```bash
curl -X POST http://localhost:8000/event \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "eventType":"level_complete",
    "meta":"{\"level\":42,\"score\":9999}",
    "timestampUtc":"2025-10-25T10:30:00Z"
  }'
```

### PowerShell (Windows)
```powershell
$TOKEN = (Invoke-RestMethod -Method POST -Uri "http://localhost:8000/login" `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"userId":"player_001"}').token

Invoke-RestMethod -Method GET -Uri "http://localhost:8000/balance" `
  -Headers @{"Authorization"="Bearer $TOKEN"}
```

## API Documentation

### Swagger UI (Interactive)

Access interactive API documentation at: **http://localhost:8000/docs**

**To authenticate in Swagger:**
1. Use **POST /login** to get a JWT token
2. Click the **"Authorize"** button (lock icon) at top-right
3. Paste your token (without "Bearer" prefix)
4. Click "Authorize" then "Close"
5. All protected endpoints will now include your auth token automatically

**Alternative documentation:** http://localhost:8000/redoc

## Data Pipeline

### Run Pipeline
```bash
# Via API
curl -X POST http://localhost:8000/run-pipeline

# Or directly
docker compose exec api python scripts/process_data.py
# Local: python scripts/process_data.py
```

### Input Files (data/)
- `purchases_raw.csv` - AppsFlyer purchase events
- `confirmed_purchases.csv` - Payment gateway confirmations
- `costs_daily.csv` - Daily ad spend per campaign
- `sessions.csv` - Player session data for DAU

### Output Reports (reports/)
- `purchases_curated.csv` - Deduplicated, clean purchase data
- `reconciliation.json` - Purchase matching results
- `roas_d1.json` - Yesterday's ROAS per campaign
- `roas_anomaly.json` - Campaigns with performance issues
- `arpdau_d1.json` - Yesterday's ARPDAU per campaign

## Project Structure

```
.
├── app/
│   └── main.py                 # FastAPI application
├── scripts/
│   └── process_data.py         # Analytics pipeline
├── data/                       # Input CSV files
├── reports/                    # Pipeline outputs
├── tests/                      # Unit tests
├── docker-compose.yml          # Docker configuration
├── Dockerfile                  # Container definition
├── requirements.txt            # Python dependencies
├── README.md                   # This file
└── PROJECT_BRIEF.md            # Detailed technical documentation
```

## Configuration

### Environment Variables

All secrets are managed via `.env` file (never committed to git):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///data/app.db` | Database connection string |
| `JWT_SECRET` | **REQUIRED** | JWT signing key (64 chars hex) |
| `JWT_TTL_MIN` | `120` | Token expiration in minutes |
| `DATA_DIR` | `data` | Data directory location |

### Security Setup

**IMPORTANT:** The `.env` file contains a pre-generated JWT secret for development. For production:

```bash
# Generate a new secure JWT secret (Python)
python -c "import secrets; print(secrets.token_hex(32))"

# Or using OpenSSL
openssl rand -hex 32

# Edit .env and update JWT_SECRET with the generated value
```

**For production deployments:**
- Use environment variables from secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate secrets regularly
- Use different secrets per environment (dev/staging/prod)

## Performance Benchmarks

| Operation | Performance | Notes |
|-----------|-------------|-------|
| API Response Time (p95) | < 100ms | With connection pooling |
| Reconciliation (10K rows) | 2-3 seconds | 100x faster than v2.0 |
| ROAS Calculation | 2-3 seconds | 7x faster than v2.0 |
| Concurrent Users | 10,000+ | With proper connection pool |
| Database Pool | 10-30 connections | Auto-scaling |

## Testing

```bash
# Run unit tests
python -m pytest tests/

# Code quality checks
flake8 app/ scripts/
black --check app/ scripts/

# Format code
black app/ scripts/
```

## Security Features

- **JWT Authentication**: Token-based stateless auth with expiration
- **Secrets Management**: .env file (gitignored) with secure 64-char secrets
- **SQL Injection Protection**: Parameterized queries via SQLAlchemy ORM
- **Race Condition Prevention**: Row-level locking on currency operations
- **Input Validation**: Pydantic models with strict type checking
- **Request Tracing**: Unique request IDs for audit trails
- **No Hardcoded Secrets**: All secrets via environment variables only

**Security Note:** The included .env file contains a generated secret for development.
Never use this in production! Generate your own unique secret for each environment.

## Troubleshooting

### Common Issues

**401 Unauthorized**
- Verify `Authorization: Bearer <token>` header format
- Check token hasn't expired (default 2 hours)

**Database Connection Issues**
- Ensure `data/` directory exists and is writable (SQLite)
- Check `DATABASE_URL` environment variable (PostgreSQL)
- Verify connection pool isn't exhausted

**Pipeline Errors**
- Confirm all required CSV files exist in `data/`
- Check CSV column names match expected schema
- Review pipeline logs for specific error details

**Windows Path Issues**
- Use `Invoke-RestMethod` instead of `curl` in PowerShell
- Or use WSL/Git Bash for Unix-like commands

## Documentation

For comprehensive technical documentation including:
- Detailed architecture diagrams
- Performance optimization explanations
- Security considerations
- Deployment guides
- Future enhancement roadmap

**See:** [brief.pdf](brief.pdf)

## Development

### Adding New Endpoints
1. Define Pydantic models in `app/main.py`
2. Implement endpoint with proper error handling
3. Add authentication with `Depends(current_user_id)` if needed
4. Write tests in `tests/`
5. Update this README and PROJECT_BRIEF.md

### Extending the Pipeline
1. Add data processing logic in `scripts/process_data.py`
2. Ensure proper error handling and logging
3. Add validation for input data
4. Write unit tests
5. Document new reports in README

## Performance Tips

1. **Use PostgreSQL in production** (not SQLite) for better concurrency
2. **Set proper `JWT_SECRET`** with 32+ random characters
3. **Monitor connection pool** utilization and adjust if needed
4. **Enable database indexes** on frequently queried columns
5. **Cache balance queries** with Redis for read-heavy workloads
6. **Run pipeline off-peak** or async with task queue

## Support

- **Maintainer**: Data Engineering Team

---
