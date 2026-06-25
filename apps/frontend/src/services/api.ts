import type { 
  Repository, 
  RepositoryGraphResponse, 
  NodeDetails, 
  ChatSession, 
  ChatMessage 
} from '../types';

const BASE_URL = 'http://localhost:8000/api/v1';

export const api = {
  // Graph APIs
  async getRepositories(): Promise<Repository[]> {
    const res = await fetch(`${BASE_URL}/graph/repositories`);
    if (!res.ok) throw new Error('Failed to load repositories');
    return res.json();
  },

  async analyzeRepository(url: string): Promise<{ repository_id: string; status: string }> {
    const res = await fetch(`${BASE_URL}/repositories/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to start analysis');
    }
    return res.json();
  },

  async deleteRepository(repoId: string): Promise<{ status: string; message: string }> {
    const res = await fetch(`${BASE_URL}/repositories/${repoId}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Failed to delete repository');
    return res.json();
  },

  async getRepositoryGraph(repoId: string): Promise<RepositoryGraphResponse> {
    const res = await fetch(`${BASE_URL}/graph/repositories/${repoId}/data`);
    if (!res.ok) throw new Error('Failed to load repository graph');
    return res.json();
  },

  async expandNode(repoId: string, nodeId: string): Promise<RepositoryGraphResponse> {
    const res = await fetch(`${BASE_URL}/graph/repositories/${repoId}/expand/${encodeURIComponent(nodeId)}`);
    if (!res.ok) throw new Error('Failed to expand node');
    return res.json();
  },

  async getNodeDetails(nodeId: string, repoId: string): Promise<NodeDetails> {
    const res = await fetch(`${BASE_URL}/graph/nodes/${encodeURIComponent(nodeId)}?repo_id=${encodeURIComponent(repoId)}`);
    if (!res.ok) throw new Error('Failed to get node details');
    return res.json();
  },

  async traverseNode(nodeId: string): Promise<RepositoryGraphResponse> {
    const res = await fetch(`${BASE_URL}/graph/nodes/${encodeURIComponent(nodeId)}/traversal`);
    if (!res.ok) throw new Error('Failed to traverse node call paths');
    return res.json();
  },

  // Chat APIs
  async createChatSession(repoId: string): Promise<ChatSession> {
    const res = await fetch(`${BASE_URL}/chat/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repository_id: repoId })
    });
    if (!res.ok) throw new Error('Failed to start chat session');
    return res.json();
  },

  async getChatSession(sessionId: string): Promise<ChatSession> {
    const res = await fetch(`${BASE_URL}/chat/sessions/${sessionId}`);
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
    const res = await fetch(`${BASE_URL}/chat/sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
