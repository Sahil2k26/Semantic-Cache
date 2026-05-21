import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { MessageSquare, Send, Settings, LogOut, User, Bot, Zap, PlusCircle } from 'lucide-react';
import { chatApi } from '../services/api';
import type { ChatMessage, ChatResponse } from '../services/api';

export default function Chat() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string>(() => crypto.randomUUID());
  
  const token = localStorage.getItem('sc_chat_token');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!token) {
      navigate('/');
    }
  }, [token, navigate]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!input.trim() || !token) return;

    const userMessage: ChatMessage = { role: 'user', content: input };
    const currentHistory = [...messages];
    
    setMessages([...currentHistory, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Simulate network request if API isn't up, otherwise use API
      const response = await chatApi.sendMessage(
        userMessage.content,
        token,
        conversationId,
        currentHistory
      ).catch(() => {
        // Fallback for demo purposes if backend isn't running
        console.log('API not reachable, using mock response');
        return new Promise<ChatResponse>(resolve => {
          setTimeout(() => {
            resolve({
              route: 'mock_fallback',
              hit: false,
              response: "This is a mock response because the backend API couldn't be reached. Ensure Semantic-Cache is running on localhost:8000.",
              cache_level: 'none',
              latency_ms: 1500
            });
          }, 1500);
        });
      });

      setMessages(prev => [...prev, { role: 'assistant', content: response.response }]);
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I encountered an error connecting to the Semantic-Cache API." }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setConversationId(crypto.randomUUID());
  };

  const handleLogout = () => {
    localStorage.removeItem('sc_chat_token');
    localStorage.removeItem('sc_tenant_id');
    navigate('/');
  };

  return (
    <div className="app-layout animate-fade-in">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Zap size={20} className="text-gradient" />
            <span style={{ fontWeight: 600, fontSize: '1.125rem' }}>Semantic Chat</span>
          </div>
          <button className="btn-icon" onClick={startNewChat} title="New Chat">
            <PlusCircle size={20} />
          </button>
        </div>
        
        <div className="sidebar-content">
          <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.5rem', fontWeight: 600 }}>
            Recent Sessions
          </div>
          <div className="chat-history-item active">
            <MessageSquare size={16} />
            <span>Current Session</span>
          </div>
        </div>

        <div className="sidebar-footer">
          <button className="btn-secondary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '0.75rem' }} onClick={handleLogout}>
            <LogOut size={16} /> Logout
          </button>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="main-content">
        <div className="chat-header">
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontWeight: 500 }}>Default Domain</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Using general context</span>
          </div>
          <button className="btn-icon">
            <Settings size={20} />
          </button>
        </div>

        <div className="messages-container">
          {messages.length === 0 ? (
            <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
              <div className="btn-icon" style={{ background: 'rgba(99, 102, 241, 0.1)', color: 'var(--accent-primary)', width: '4rem', height: '4rem', marginBottom: '1rem' }}>
                <Zap size={32} />
              </div>
              <h2 style={{ color: 'var(--text-primary)', marginBottom: '0.5rem' }}>How can I help you today?</h2>
              <p>Type a message to start caching context.</p>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className="message-wrapper">
                <div className="message">
                  <div className={`message-avatar ${msg.role === 'user' ? 'avatar-user' : 'avatar-assistant'}`}>
                    {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                  </div>
                  <div className="message-content">
                    <p style={{ fontWeight: 600, marginBottom: '0.25rem', color: msg.role === 'user' ? 'var(--text-secondary)' : 'var(--accent-primary)' }}>
                      {msg.role === 'user' ? 'You' : 'Semantic AI'}
                    </p>
                    <p>{msg.content}</p>
                  </div>
                </div>
              </div>
            ))
          )}
          
          {isLoading && (
            <div className="message-wrapper">
              <div className="message">
                <div className="message-avatar avatar-assistant">
                  <Bot size={16} />
                </div>
                <div className="message-content" style={{ display: 'flex', alignItems: 'center' }}>
                  <div className="typing-indicator">
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-area-wrapper">
          <div className="input-container">
            <textarea
              className="chat-input"
              placeholder="Message Semantic Cache..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              rows={1}
            />
            <button 
              className="send-button"
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
            >
              <Send size={16} />
            </button>
          </div>
          <div style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
            Semantic-Cache can route queries to specific models and store context history.
          </div>
        </div>
      </div>
    </div>
  );
}
