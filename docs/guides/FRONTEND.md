# Web Visual Suite Guide

This guide details the architecture, configuration, and interface features of the **Web Visual Suite**—composed of two specialized Next.js web applications designed to monitor and demo the semantic caching microservice.

---

## 🗺️ Architectural Context

The visual applications sit on top of the backend API, consuming REST endpoints, Server-Sent Events (SSE) streaming connections, and real-time WebSockets to provide a visual playground:

```
                      ┌─────────────────────────┐
                      │    Next.js Dashboard    │ (Port 3000)
                      └────────────┬────────────┘
                                   │ WS /ws/realtime
                                   ▼
┌────────────────────────────────────────────────────────────────┐
│                     FastAPI Cache Backend                      │ (Port 8000)
└──────────────────────────────────▲─────────────────────────────┘
                                   │ HTTP POST /chat
                                   ▼
                      ┌─────────────────────────┐
                      │    Next.js Chat App     │ (Port 3001)
                      └─────────────────────────┘
```

---

## 📈 The Analytics Dashboard (`frontend-services/dashboard`)

The dashboard offers a control-room interface visualizing total cost savings, average backend response times, and storage tier partition hit splits in real-time.

### 🧩 Core Visual Features
1. **Real-time WebSockets:** Connects to `ws://localhost:8000/ws/realtime` to capture live query counts, hit rates, and tier latency states.
2. **Interactive Charting (Recharts):** Plots dynamic time-series charts detailing L1 vs L2 vs L3 hit distributions, active throughput (qps), and cumulative dollars saved compared to raw LLM calls.
3. **Top Queries Leaderboard:** Visualizes hot queries, displaying hit counts, average latency, and source domains.

### ⚙️ Quick Start
```bash
# Navigate to dashboard root
cd frontend-services/dashboard

# Install packages
npm install

# Start Next.js server
npm run dev
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser to inspect live metrics.

---

## 💬 The Consumer Chat App (`frontend-services/chat-app`)

The consumer chat client provides a chat dialogue interface demonstrating stateless query indexing and context-aware session routing.

### 🧩 Core Demo Features
1. **Interactive Latency Badging:** Every response displays a latency badge (e.g., `Memory L1: 1.2ms` or `Warm L2: 7.4ms` or `Postgres L3: 22ms` or `Gemini: 1450ms`) to verify cache performance gains.
2. **Context-Aware Sandbox:** Automatically appends conversation turns to custom HTTP headers (`X-Conversation-History`) and identifiers (`X-Conversation-Id`), demonstrating the Smart Routing layer.
3. **SSE Streaming Demonstration:** Visualizes real-time token stream playback utilizing Server-Sent Events (SSE).

### ⚙️ Quick Start
```bash
# Navigate to chat app root
cd frontend-services/chat-app

# Install packages
npm install

# Start Next.js server
npm run dev
```
Open **[http://localhost:3001](http://localhost:3001)** to start a conversation.

---

## 🛠️ Environment Variables Configuration

Both web applications are configured via a `.env.local` file inside their respective folder roots:

### Dashboard Environment (`.env.local`)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/realtime
```

### Chat Application Environment (`.env.local`)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```
