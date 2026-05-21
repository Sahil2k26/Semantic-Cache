export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  route: string;
  hit: boolean;
  response: string;
  context_used?: boolean;
  conversation_id?: string;
  cache_level?: string;
  latency_ms?: number;
}

const API_BASE_URL = 'http://localhost:8000';

export const chatApi = {
  async sendMessage(
    query: string, 
    token: string, 
    conversationId: string, 
    history: ChatMessage[],
    domain: string = 'general'
  ): Promise<ChatResponse> {
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    };

    if (conversationId) {
      headers['X-Conversation-Id'] = conversationId;
    }
    
    if (history && history.length > 0) {
      headers['X-Conversation-History'] = JSON.stringify(history);
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/cache/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          query,
          domain,
          history,
          context_id: conversationId
        })
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Chat API Error:', error);
      throw error;
    }
  }
};
