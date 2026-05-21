'use client';
import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Network, LineChart, Activity, Zap } from 'lucide-react';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const navItems = [
    { name: 'Overview', path: '/', icon: LayoutDashboard },
    { name: 'Query Patterns', path: '/patterns', icon: Network },
    { name: 'Semantic Clusters', path: '/clusters', icon: Activity },
    { name: 'Cost Analytics', path: '/cost', icon: LineChart },
  ];

  return (
    <div className="dashboard-container">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <Zap size={24} color="var(--accent-primary)" fill="var(--accent-primary)" />
          <span className="text-gradient">Semantic Cache</span>
        </div>
        
        <div className="nav-group">
          <div className="nav-title">Analytics</div>
          {navItems.map((item) => (
            <Link 
              key={item.path} 
              href={item.path} 
              className={`nav-item ${pathname === item.path ? 'active' : ''}`}
            >
              <item.icon size={18} />
              {item.name}
            </Link>
          ))}
        </div>
      </aside>
      
      <main className="dashboard-content">
        {children}
      </main>
    </div>
  );
}
