
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY app /app/app
COPY scripts /app/scripts
COPY data /app/data
RUN mkdir -p /app/reports
ENV DATA_DIR=/app/data
ENV DATABASE_URL=sqlite:////app/data/app.db
ENV JWT_TTL_MIN=120
# JWT_SECRET must be provided via docker-compose.yml or runtime environment
# Do NOT hardcode secrets in Dockerfile.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
