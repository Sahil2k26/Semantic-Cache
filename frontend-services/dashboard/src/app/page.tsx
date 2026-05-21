'use client';
import React, { useEffect, useState } from 'react';
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { ArrowUpRight, Activity, Clock, Database, Search } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api/v1';
const WS_BASE = 'ws://localhost:8000/ws/realtime';

export default function OverviewPage() {
  const [realtimeData, setRealtimeData] = useState<any>({
    hit_rate: 0,
    semantic_hit_rate: 0,
    timestamp: new Date().toISOString()
  });
  const [historyData, setHistoryData] = useState<any[]>([]);
  const [topQueries, setTopQueries] = useState<any[]>([]);
  const [wsStatus, setWsStatus] = useState('Connecting...');

  useEffect(() => {
    /* 
    // TODO: Uncomment when connecting to actual backend
    // 1. Fetch Top Queries
    fetch(`${API_BASE}/insights/top-queries?limit=5`)
      .then(res => res.json())
      .then(data => setTopQueries(Array.isArray(data) ? data : []))
      .catch(console.error);

    // 2. Fetch Historical for Chart
    const end = new Date().toISOString();
    const start = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    fetch(`${API_BASE}/metrics/historical?start=${start}&end=${end}&granularity=1h`)
      .then(res => res.json())
      .then(res => {
         if (res && res.data && res.data.length > 0) setHistoryData(res.data);
      })
      .catch(console.error);

    // 3. Setup WebSocket
    const ws = new WebSocket(WS_BASE);
    ws.onopen = () => setWsStatus('Connected');
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setRealtimeData(data);
      } catch (e) {}
    };
    ws.onclose = () => setWsStatus('Disconnected');
    ws.onerror = () => setWsStatus('Error');

    return () => {
      if (ws.readyState === 1) {
        ws.close();
      }
    };
    */

    // DUMMY DATA LOGIC
    setTopQueries([
      { query_hash: 'What is the capital of France?', access_count: 142 },
      { query_hash: 'How to build a semantic cache', access_count: 98 },
      { query_hash: 'Difference between REST and GraphQL', access_count: 76 },
      { query_hash: 'FastAPI dependency injection', access_count: 45 },
      { query_hash: 'React hooks lifecycle', access_count: 32 },
    ]);

    setHistoryData([
      { time: '00:00', hit_rate: 0.42 }, { time: '04:00', hit_rate: 0.48 },
      { time: '08:00', hit_rate: 0.55 }, { time: '12:00', hit_rate: 0.76 },
      { time: '16:00', hit_rate: 0.81 }, { time: '20:00', hit_rate: 0.79 },
      { time: '24:00', hit_rate: 0.85 },
    ]);

    setRealtimeData({
      hit_rate: 0.82,
      semantic_hit_rate: 0.45,
      timestamp: new Date().toISOString()
    });
    setWsStatus('Dummy Data');
  }, []);

  return (
    <div className="animate-fade-in">
      <header style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Dashboard Overview</h1>
          <p className="text-muted">Real-time cache performance and semantics</p>
        </div>
        <div className={`status-badge ${wsStatus === 'Connected' ? 'healthy' : 'warning'}`}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: wsStatus === 'Connected' ? 'var(--success)' : 'var(--warning)', marginRight: '4px' }} className={wsStatus === 'Connected' ? 'animate-pulse' : ''}></div>
          WS: {wsStatus}
        </div>
      </header>

      {/* Stats row */}
      <div className="stats-grid">
        <div className="glass-card stat-card">
          <div className="stat-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Activity size={16}/> Global Hit Rate</div>
          <div className="stat-value">
            {(realtimeData.hit_rate * 100).toFixed(1)}%
            <span className="stat-change positive" style={{ display: 'flex', alignItems: 'center' }}><ArrowUpRight size={14}/> +2.4%</span>
          </div>
        </div>
        
        <div className="glass-card stat-card">
          <div className="stat-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Database size={16}/> Semantic Hit Rate</div>
          <div className="stat-value">
            {(realtimeData.semantic_hit_rate * 100).toFixed(1)}%
            <span className="stat-change positive" style={{ display: 'flex', alignItems: 'center' }}><ArrowUpRight size={14}/> +5.1%</span>
          </div>
        </div>

        <div className="glass-card stat-card">
          <div className="stat-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><Clock size={16}/> Avg Latency</div>
          <div className="stat-value">
            45<span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>ms</span>
            <span className="stat-change neutral">--</span>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: '1.5rem', marginBottom: '2rem' }}>
        {/* Main Chart */}
        <div className="glass-card">
          <h3 style={{ marginBottom: '1.5rem' }}>Hit Rate Trend (24h)</h3>
          <div style={{ height: '300px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={historyData}>
                <defs>
                  <linearGradient id="colorHitRate" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" vertical={false} />
                <XAxis dataKey="time" stroke="var(--text-muted)" tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-muted)" tickLine={false} axisLine={false} tickFormatter={(tick) => `${(tick * 100).toFixed(0)}%`} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                  itemStyle={{ color: 'var(--text-primary)' }}
                />
                <Area type="monotone" dataKey="hit_rate" stroke="var(--accent-primary)" strokeWidth={3} fillOpacity={1} fill="url(#colorHitRate)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top Queries */}
        <div className="glass-card" style={{ display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Search size={18}/> Top Semantic Hits
          </h3>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {topQueries && topQueries.length > 0 ? topQueries.map((query, idx) => (
              <div key={idx} style={{ padding: '0.75rem 0', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '150px' }}>
                  {query.query_hash}
                </span>
                <span className="status-badge healthy">{query.access_count} hits</span>
              </div>
            )) : (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '2rem 0' }}>
                No significant hits yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
