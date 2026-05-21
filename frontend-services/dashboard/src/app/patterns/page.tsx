'use client';
import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Network, Activity, Clock } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api/v1';

export default function PatternsPage() {
  const [patterns, setPatterns] = useState<any[]>([]);
  const [recentQueries, setRecentQueries] = useState<any[]>([]);

  useEffect(() => {
    /*
    // TODO: Uncomment when connecting to actual backend
    fetch(`${API_BASE}/insights/patterns`)
      .then(res => res.json())
      .then(data => setPatterns(data))
      .catch(console.error);

    fetch(`${API_BASE}/insights/recent?limit=10`)
      .then(res => res.json())
      .then(data => setRecentQueries(data))
      .catch(console.error);
    */

    // DUMMY DATA LOGIC
    setPatterns([
      { name: 'Greeting', count: 120 },
      { name: 'Fact Retrieval', count: 350 },
      { name: 'Summarization', count: 210 },
      { name: 'Translation', count: 80 },
      { name: 'Code Gen', count: 150 },
    ]);

    setRecentQueries([
      { id: '1', query: 'Write a python script for...', status: 'HIT', latency: '12ms', time: '10:05 AM' },
      { id: '2', query: 'Summarize this article...', status: 'MISS', latency: '850ms', time: '10:06 AM' },
      { id: '3', query: 'Translate Hello to Spanish', status: 'HIT', latency: '8ms', time: '10:08 AM' },
      { id: '4', query: 'What is the speed of light?', status: 'HIT', latency: '11ms', time: '10:10 AM' },
      { id: '5', query: 'Create a react component...', status: 'MISS', latency: '1200ms', time: '10:15 AM' },
    ]);
  }, []);

  return (
    <div className="animate-fade-in">
      <header style={{ marginBottom: '2rem' }}>
        <h1>Query Patterns</h1>
        <p className="text-muted">Analyze how your cache is being queried</p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: '1.5rem', marginBottom: '2rem' }}>
        <div className="glass-card">
          <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Network size={18}/> Pattern Distribution
          </h3>
          <div style={{ height: '300px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={patterns}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" vertical={false} />
                <XAxis dataKey="name" stroke="var(--text-muted)" tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-muted)" tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                  itemStyle={{ color: 'var(--text-primary)' }}
                  cursor={{ fill: 'var(--bg-elevated)' }}
                />
                <Bar dataKey="count" fill="var(--accent-primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass-card" style={{ display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Activity size={18}/> Recent Queries
          </h3>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {recentQueries.map((q) => (
              <div key={q.id} style={{ padding: '0.75rem 0', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                  <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{q.query}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <Clock size={12}/> {q.time} • Latency: {q.latency}
                  </span>
                </div>
                <span className={`status-badge ${q.status === 'HIT' ? 'healthy' : 'warning'}`}>
                  {q.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
