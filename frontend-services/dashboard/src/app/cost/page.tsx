'use client';
import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { LineChart as LineChartIcon, DollarSign, ArrowDown } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api/v1';

export default function CostPage() {
  const [costData, setCostData] = useState<any[]>([]);
  const [totalSaved, setTotalSaved] = useState(0);

  useEffect(() => {
    /*
    // TODO: Uncomment when connecting to actual backend
    fetch(`${API_BASE}/metrics/cost`)
      .then(res => res.json())
      .then(data => {
         setCostData(data.history || []);
         setTotalSaved(data.total_saved || 0);
      })
      .catch(console.error);
    */

    // DUMMY DATA LOGIC
    setCostData([
      { date: 'Mon', actualCost: 12.5, savedCost: 5.2 },
      { date: 'Tue', actualCost: 15.0, savedCost: 8.5 },
      { date: 'Wed', actualCost: 10.2, savedCost: 6.1 },
      { date: 'Thu', actualCost: 18.5, savedCost: 12.4 },
      { date: 'Fri', actualCost: 22.1, savedCost: 15.8 },
      { date: 'Sat', actualCost: 14.5, savedCost: 9.2 },
      { date: 'Sun', actualCost: 9.5,  savedCost: 4.5 },
    ]);
    setTotalSaved(61.7);
  }, []);

  return (
    <div className="animate-fade-in">
      <header style={{ marginBottom: '2rem' }}>
        <h1>Cost Analytics</h1>
        <p className="text-muted">Track API cost savings through semantic caching</p>
      </header>

      <div className="stats-grid" style={{ marginBottom: '2rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem' }}>
        <div className="glass-card stat-card">
          <div className="stat-label" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><DollarSign size={16}/> Total Saved (7d)</div>
          <div className="stat-value" style={{ color: 'var(--success)' }}>
            ${totalSaved.toFixed(2)}
            <span className="stat-change positive" style={{ display: 'flex', alignItems: 'center', fontSize: '0.9rem' }}><ArrowDown size={14}/> 35%</span>
          </div>
        </div>
      </div>

      <div className="glass-card">
        <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <LineChartIcon size={18}/> API Cost vs Savings
        </h3>
        <div style={{ height: '400px', width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={costData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" vertical={false} />
              <XAxis dataKey="date" stroke="var(--text-muted)" tickLine={false} axisLine={false} />
              <YAxis stroke="var(--text-muted)" tickLine={false} axisLine={false} tickFormatter={(value) => `$${value}`} />
              <Tooltip 
                contentStyle={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                itemStyle={{ color: 'var(--text-primary)' }}
              />
              <Legend wrapperStyle={{ paddingTop: '20px' }} />
              <Line type="monotone" name="Cost Incurred" dataKey="actualCost" stroke="var(--accent-secondary)" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              <Line type="monotone" name="Cost Saved" dataKey="savedCost" stroke="var(--success)" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
