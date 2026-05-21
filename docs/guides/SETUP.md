# Local Environment & Services Setup

This guide details instructions on setting up your local development environment, configuring backing database and caching services, running tests, and starting backend/frontend applications.

---

## 🚀 Backend Setup

### 1. Prerequisites
- **Python 3.10+** (Required)
- **Docker & Docker Compose** (Required)
- **Node.js 18+** (Required for frontend applications)

### 2. Install Dependencies & Virtual Environment
Clone the repository and initialize your python virtual environment:
```bash
# Initialize venv
python -m venv venv

# Activate venv (Windows)
.\venv\Scripts\activate

# Activate venv (macOS/Linux)
source venv/bin/activate

# Install core backend dependencies
pip install -r requirements.txt
```

### 3. Docker Infrastructure Setup
Use Docker Compose to provision PostgreSQL with the `pgvector` extension, Redis warm cache, Prometheus metrics collector, and Grafana visual monitoring.
```bash
# Start infrastructure containers
docker-compose up -d

# Verify that all 4 containers are running
docker-compose ps
```

---

## ⚙️ Environment Configuration

Create a `.env` file in the root workspace folder to enable the modular LLM Service fallback and tiered backends:

```env
# API Server Bind Config
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false

# Redis Warm Cache (L2)
REDIS_HOST=localhost
REDIS_PORT=6379

# PostgreSQL Cold Store (L3) with pgvector
DATABASE_URL=postgresql://semantic_cache:semantic_cache_dev@localhost/semantic_cache

# Embedding Model (Sentence Transformers)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Modular LLM Miss Fallback Configuration (Phase 9)
LLM_PROVIDER=gemini
LLM_API_KEY=YOUR_GOOGLE_GENERATIVE_AI_API_KEY

# Logging Level
LOG_LEVEL=INFO
```

---

## 🖥️ Starting the Services

### 1. Start Backend FastAPI Server
Once environment variables are configured, spin up the FastAPI ASGI server:
```bash
python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```
- **Interactive OpenAPI (Swagger) Docs:** http://localhost:8000/docs
- **ReDoc Guides:** http://localhost:8000/redoc

### 2. Verify with Unit Tests
Execute the comprehensive Pytest suite to verify cache mechanics and LLM mocked integration:
```bash
# Run backend tests
pytest tests/ -v
```

---

## 🎨 Frontend Web Applications Setup

The project features a **Web Visual Suite** composed of two Next.js React applications. Make sure you have **Node.js (18+)** installed.

### 1. The Analytics Dashboard (`frontend-services/dashboard`)
Visualizes Cache hit partitions (L1/L2/L3), token timings, and cost savings in real-time using WebSockets.

```bash
# Navigate to directory
cd frontend-services/dashboard

# Install node dependencies
npm install

# Start Next.js development server
npm run dev
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser to inspect hit performance.

### 2. The Consumer Chat Application (`frontend-services/chat-app`)
A chat client designed to test context-aware session routing (`/chat`) with integrated LLM latency feedback badges.

```bash
# Navigate to directory
cd frontend-services/chat-app

# Install dependencies
npm install

# Start Next.js server
npm run dev
```
Open **[http://localhost:3001](http://localhost:3001)** to chat with the system.

---

## 📈 Monitoring Stack

Once the Docker Compose containers are healthy:
- **Grafana Metrics Dashboard:** http://localhost:3000 (Credentials: `admin`/`admin`)
- **Prometheus Collector:** http://localhost:9090
