# Production Deployment Guide

This document outlines standard procedures for deploying the multi-tier semantic cache microservice and its accompanying Next.js visual frontends to production clusters.

---

## 🚀 Backend Service Deployment

### 1. Containerized Stack (Recommended)
The fastest path to production is deploying the backend service via the optimized production Docker Compose file:

```bash
# Build and run with production settings
docker-compose -f docker-compose.prod.yml up --build -d
```

### 2. Microservice Scale-out (Kubernetes)
For high-availability clusters, scale out Uvicorn workers and cache nodes horizontally:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: semantic-cache-api
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        image: semantic-cache-api:latest
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: cache-secrets
              key: db-url
        - name: REDIS_HOST
          value: "redis-cluster.cache.svc.cluster.local"
```

> [!IMPORTANT]
> When scaling out behind a Load Balancer, the L1 caches remain synchronized in real-time across instances using built-in Redis Pub/Sub invalidation events (`src/cache/l2_cache.py`).

---

## 🎨 Next.js Frontends Deployment

Deploy the Visual Suite (`dashboard` and `chat-app`) to high-performance cloud providers (Vercel, AWS ECS, or Docker).

### 1. Vercel deployment (Recommended)
Both applications are standard Next.js apps, allowing seamless deployment to **Vercel**:
1. Connect your Git repository to Vercel.
2. Set the **Root Directory** to `frontend-services/dashboard` or `frontend-services/chat-app`.
3. Set the Environment Variables as listed below.
4. Click **Deploy**.

### 2. Docker Deployment
Use multi-stage Dockerfiles inside each frontend folder to build highly compact production images:

```dockerfile
# Example Next.js production stage
FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
```

---

## ⚙️ Production Environment Checklist

Before deploying, ensure all of the following environment keys are populated:

### Backend Service API
- `DATABASE_URL` — Production PostgreSQL database string (e.g., AWS RDS or Supabase).
- `REDIS_HOST` & `REDIS_PORT` — Managed Redis Cache instance (e.g., ElastiCache or Redis Labs).
- `LLM_PROVIDER` — `"gemini"` or `"openai"`.
- `LLM_API_KEY` — Production API token with proper billing quotas set.

### Next.js Dashboard
- `NEXT_PUBLIC_API_URL` — `http://your-production-backend-url`
- `NEXT_PUBLIC_WS_URL` — `ws://your-production-backend-url/ws/realtime`

### Next.js Chat Client
- `NEXT_PUBLIC_API_URL` — `http://your-production-backend-url`
