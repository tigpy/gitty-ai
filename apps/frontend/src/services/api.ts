import type { 
  Repository, 
  RepositoryGraphResponse, 
  NodeDetails, 
  ChatSession, 
  ChatMessage,
  User,
  TokenResponse
} from '../types';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const TOKEN_KEY = 'gitty_access_token';

async function fetchWithAuth(input: string, init: RequestInit = {}): Promise<Response> {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = new Headers(init.headers || {});

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  if (!headers.has('Content-Type') && init.body && typeof init.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(input, {
    ...init,
    headers
  });

  return response;
}

export const api = {
  // Token Management
  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },

  setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
  },

  clearToken(): void {
    localStorage.removeItem(TOKEN_KEY);
  },

  // Auth APIs
  async register(data: { email: string; username: string; password: string }): Promise<User> {
    const res = await fetchWithAuth(`${BASE_URL}/auth/register`, {
      method: 'POST',
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
      throw new Error(err.detail || 'Registration failed');
    }
    return res.json();
  },

  async login(data: { username: string; password: string }): Promise<TokenResponse> {
    const res = await fetchWithAuth(`${BASE_URL}/auth/login`, {
      method: 'POST',
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Invalid credentials' }));
      throw new Error(err.detail || 'Login failed');
    }
    const tokenData: TokenResponse = await res.json();
    this.setToken(tokenData.access_token);
    return tokenData;
  },

  async getMe(): Promise<User> {
    const res = await fetchWithAuth(`${BASE_URL}/auth/me`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Unauthorized' }));
      throw new Error(err.detail || 'Unauthorized');
    }
    return res.json();
  },

  // SSE Progress URL helper
  getProgressUrl(repoId: string): string {
    const token = this.getToken();
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${BASE_URL}/repositories/${repoId}/progress${tokenParam}`;
  },

  // Graph APIs
  async getRepositories(): Promise<Repository[]> {
    const res = await fetchWithAuth(`${BASE_URL}/graph/repositories`);
    if (!res.ok) throw new Error('Failed to load repositories');
    return res.json();
  },

  async analyzeRepository(url: string): Promise<{ repository_id: string; status: string }> {
    const res = await fetchWithAuth(`${BASE_URL}/repositories/analyze`, {
      method: 'POST',
      body: JSON.stringify({ url })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to start analysis' }));
      throw new Error(err.detail || 'Failed to start analysis');
    }
    return res.json();
  },

  async deleteRepository(repoId: string): Promise<{ status: string; message: string }> {
    const res = await fetchWithAuth(`${BASE_URL}/repositories/${repoId}`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to delete repository' }));
      throw new Error(err.detail || 'Failed to delete repository');
    }
    return res.json();
  },

  async getRepositoryGraph(repoId: string): Promise<RepositoryGraphResponse> {
    const res = await fetchWithAuth(`${BASE_URL}/graph/repositories/${repoId}/data`);
    if (!res.ok) throw new Error('Failed to load repository graph');
    return res.json();
  },

  async expandNode(repoId: string, nodeId: string): Promise<RepositoryGraphResponse> {
    const res = await fetchWithAuth(`${BASE_URL}/graph/repositories/${repoId}/expand/${encodeURIComponent(nodeId)}`);
    if (!res.ok) throw new Error('Failed to expand node');
    return res.json();
  },

  async getNodeDetails(nodeId: string, repoId: string): Promise<NodeDetails> {
    const res = await fetchWithAuth(`${BASE_URL}/graph/nodes/${encodeURIComponent(nodeId)}?repo_id=${encodeURIComponent(repoId)}`);
    if (!res.ok) throw new Error('Failed to get node details');
    return res.json();
  },

  async traverseNode(nodeId: string): Promise<RepositoryGraphResponse> {
    const res = await fetchWithAuth(`${BASE_URL}/graph/nodes/${encodeURIComponent(nodeId)}/traversal`);
    if (!res.ok) throw new Error('Failed to traverse node call paths');
    return res.json();
  },

  // Chat APIs
  async createChatSession(repoId: string): Promise<ChatSession> {
    const res = await fetchWithAuth(`${BASE_URL}/chat/sessions`, {
      method: 'POST',
      body: JSON.stringify({ repository_id: repoId })
    });
    if (!res.ok) throw new Error('Failed to start chat session');
    return res.json();
  },

  async getChatSession(sessionId: string): Promise<ChatSession> {
    const res = await fetchWithAuth(`${BASE_URL}/chat/sessions/${sessionId}`);
    if (!res.ok) throw new Error('Failed to load chat history');
    return res.json();
  },

  async sendChatMessage(
    sessionId: string, 
    content: string, 
    options?: {
      include_code?: boolean;
      include_docs?: boolean;
      include_security?: boolean;
      limit?: number;
      min_score?: number;
    }
  ): Promise<ChatMessage> {
    const res = await fetchWithAuth(`${BASE_URL}/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, ...options })
    });
    if (!res.ok) {
      const err = new Error('Failed to send message') as any;
      err.status = res.status;
      throw err;
    }
    return res.json();
  }
};
