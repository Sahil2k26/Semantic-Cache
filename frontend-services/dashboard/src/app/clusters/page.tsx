'use client';
import React, { useEffect, useState } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Layers } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api/v1';

export default function ClustersPage() {
  const [clusters, setClusters] = useState<any[]>([]);

  useEffect(() => {
    /*
    // TODO: Uncomment when connecting to actual backend
    fetch(`${API_BASE}/insights/clusters`)
      .then(res => res.json())
      .then(data => setClusters(data))
      .catch(console.error);
    */

    // DUMMY DATA LOGIC
    // Simulating 2D projection of semantic clusters
    const dummyClusters = [];
    for (let i = 0; i < 50; i++) {
      dummyClusters.push({
        x: Math.random() * 100,
        y: Math.random() * 100,
        z: Math.random() * 500 + 50, // size
        category: ['Tech', 'Science', 'Health', 'General'][Math.floor(Math.random() * 4)]
      });
    }
    setClusters(dummyClusters);
  }, []);

  const COLORS: { [key: string]: string } = {
    'Tech': '#3b82f6',
    'Science': '#10b981',
    'Health': '#ef4444',
    'General': '#f59e0b'
  };

  return (
    <div className="animate-fade-in">
      <header style={{ marginBottom: '2rem' }}>
        <h1>Semantic Clusters</h1>
        <p className="text-muted">Visualize query embeddings in 2D space</p>
      </header>

      <div className="glass-card" style={{ marginBottom: '2rem' }}>
        <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Layers size={18}/> 2D Embedding Projection
        </h3>
        <div style={{ height: '500px', width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
              <XAxis type="number" dataKey="x" name="Dimension 1" stroke="var(--text-muted)" tickLine={false} axisLine={false} />
              <YAxis type="number" dataKey="y" name="Dimension 2" stroke="var(--text-muted)" tickLine={false} axisLine={false} />
              <Tooltip 
                cursor={{ strokeDasharray: '3 3' }} 
                contentStyle={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                itemStyle={{ color: 'var(--text-primary)' }}
              />
              <Scatter name="Queries" data={clusters} fill="var(--accent-primary)">
                {clusters.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[entry.category] || 'var(--accent-primary)'} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '1rem' }}>
          {Object.keys(COLORS).map(cat => (
            <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: COLORS[cat] }}></div>
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{cat}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
