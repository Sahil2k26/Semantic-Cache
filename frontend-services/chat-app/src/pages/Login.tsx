import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound, ArrowRight } from 'lucide-react';

export default function Login() {
  const [token, setToken] = useState('');
  const [tenant, setTenant] = useState('');
  const navigate = useNavigate();

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (token) {
      // For now, simply save the token to local storage and proceed
      localStorage.setItem('sc_chat_token', token);
      if (tenant) {
        localStorage.setItem('sc_tenant_id', tenant);
      }
      navigate('/chat');
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card glass-panel animate-fade-in">
        <div className="auth-header">
          <div className="btn-icon" style={{ margin: '0 auto 1rem', background: 'rgba(99, 102, 241, 0.1)', color: 'var(--accent-primary)', width: '3rem', height: '3rem' }}>
            <KeyRound size={24} />
          </div>
          <h1 className="text-gradient">Welcome Back</h1>
          <p>Sign in to Semantic-Cache Chat</p>
        </div>

        <form onSubmit={handleLogin} className="auth-form">
          <div className="form-group">
            <label htmlFor="token">JWT Auth Token</label>
            <input 
              type="password" 
              id="token" 
              className="input-field" 
              placeholder="eyJhbGci..." 
              value={token}
              onChange={(e) => setToken(e.target.value)}
              required 
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="tenant">Tenant ID (Optional)</label>
            <input 
              type="text" 
              id="tenant" 
              className="input-field" 
              placeholder="tenant_abc123"
              value={tenant}
              onChange={(e) => setTenant(e.target.value)} 
            />
          </div>

          <button type="submit" className="btn btn-primary" style={{ marginTop: '1rem', width: '100%', padding: '0.75rem' }}>
            Sign In <ArrowRight size={16} style={{ marginLeft: '0.5rem' }} />
          </button>
        </form>
      </div>
    </div>
  );
}
