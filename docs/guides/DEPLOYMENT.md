# Semantic Cache - Production Deployment Guide

This document outlines how to deploy the Semantic Cache layer in a production environment.

## Prerequisites
- Docker and Docker Compose installed
- At least 4 CPU cores and 8GB RAM available
- Python 3.12+ (if deploying natively without Docker)

## Deployment via Docker Compose (Recommended)
We have provided a `docker-compose.prod.yml` that includes optimized settings for production traffic including Uvicorn workers and Redis memory policies.

### Steps
1. Ensure that `docker-compose` is available on your server.
2. Spin up the services in detached mode using the production compose file:
   ```bash
   docker-compose -f docker-compose.prod.yml up --build -d
   ```
3. The API will be available on port 8000. 

## Security Hardening
In production, ensure you update the following environment variables in your `.env` or CI/CD secrets:
- `JWT_SECRET_KEY`: Set to a strong cryptographically generated secret.
- `CORS_ORIGINS`: Restrict this to only your frontend or backend microservices (remove `*`).
- `REDIS_PASSWORD`: Enforce a Redis password for `redis-server` and in the API configuration.

## Performance Optimizations Applied
The API already leverages Several optimizations across the stack:
- **Gzip Compression**: `GZipMiddleware` is enabled for API responses larger than 1000 bytes.
- **Connection Pooling**: Database and Redis limits are pre-configured in `src/api/config.py`.
- **Redis Pub/Sub**: The L1 cache automatically synchronizes across multi-worker architectures via Redis Pub/Sub events for immediate cache invalidation.

## Load Testing
For benchmarking your specific infrastructure, use the provided Locust script:
```bash
pip install locust
locust -f tests/performance/locustfile.py --host=http://<PRODUCTION_URL> --headless -u 100 -r 10
```
Monitor the output metrics to verify that you meet the >1000 requests/sec latency targets.
