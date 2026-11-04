import axios from 'axios';
import {
  User,
  Repository,
  RepositoryStatus,
  RepositoryFileItem,
  FileContent,
  ChatMessage,
  ChatSession,
  DebugAnalyzeResponse,
  CodeReviewResponse,
  SearchResultItem,
  AgentWorkflowResponse,
  DiffChangeResponse,
} from '../types';

export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT access token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('reposage_access_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response error handler
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear token if invalid
      localStorage.removeItem('reposage_access_token');
    }
    return Promise.reject(error);
  }
);

export const api = {
  // Auth
  register: async (email: string, password: string) => {
    const res = await apiClient.post('/auth/register', { email, password });
    return res.data.data;
  },
  login: async (email: string, password: string) => {
    const res = await apiClient.post('/auth/login', { email, password });
    return res.data.data;
  },
  getMe: async (): Promise<User> => {
    const res = await apiClient.get('/auth/me');
    return res.data.data;
  },

  // Repositories
  getRepositories: async (): Promise<Repository[]> => {
    const res = await apiClient.get('/repositories');
    return res.data.data;
  },
  getRepository: async (id: string): Promise<Repository> => {
    const res = await apiClient.get(`/repositories/${id}`);
    return res.data.data;
  },
  addGitHubRepo: async (data: { name: string; url: string; branch?: string; access_token?: string }): Promise<Repository> => {
    const res = await apiClient.post('/repositories', data);
    return res.data.data;
  },
  uploadZipRepo: async (formData: FormData): Promise<Repository> => {
    const res = await apiClient.post('/repositories/upload-zip', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data.data;
  },
  deleteRepository: async (id: string) => {
    const res = await apiClient.delete(`/repositories/${id}`);
    return res.data;
  },
  reindexRepository: async (id: string) => {
    const res = await apiClient.post(`/repositories/${id}/reindex`);
    return res.data;
  },
  getRepositoryStatus: async (id: string): Promise<RepositoryStatus> => {
    const res = await apiClient.get(`/repositories/${id}/status`);
    return res.data.data;
  },
  getRepositoryFiles: async (id: string): Promise<RepositoryFileItem[]> => {
    const res = await apiClient.get(`/repositories/${id}/files`);
    return res.data.data;
  },
  getFileContent: async (id: string, path: string): Promise<FileContent> => {
    const res = await apiClient.get(`/repositories/${id}/file-content`, {
      params: { path },
    });
    return res.data.data;
  },

  // Chat
  sendMessage: async (data: { repository_id: string; question: string; session_id?: string }): Promise<ChatMessage> => {
    const res = await apiClient.post('/chat', data);
    return res.data.data;
  },
  getSessions: async (repository_id: string): Promise<ChatSession[]> => {
    const res = await apiClient.get('/chat/sessions', { params: { repository_id } });
    return res.data.data;
  },
  getSessionMessages: async (session_id: string): Promise<ChatMessage[]> => {
    const res = await apiClient.get(`/chat/sessions/${session_id}`);
    return res.data.data;
  },
  deleteSession: async (session_id: string) => {
    const res = await apiClient.delete(`/chat/sessions/${session_id}`);
    return res.data;
  },

  // Search
  search: async (data: { repository_id: string; query: string; search_type?: string; top_k?: number; file_filter?: string }): Promise<SearchResultItem[]> => {
    const res = await apiClient.post('/search', data);
    return res.data.data.results;
  },

  // Debugging
  analyzeDebug: async (data: { repository_id: string; error_message: string; stack_trace?: string; relevant_file?: string }): Promise<DebugAnalyzeResponse> => {
    const res = await apiClient.post('/debug/analyze', data);
    return res.data.data;
  },

  // Review
  reviewCode: async (data: { repository_id: string; file_path?: string; code_snippet?: string }): Promise<CodeReviewResponse> => {
    const res = await apiClient.post('/review', data);
    return res.data.data;
  },

  // Agent Workflow
  runAgentWorkflow: async (data: { repository_id: string; query: string; session_id?: string }): Promise<AgentWorkflowResponse> => {
    const res = await apiClient.post('/chat/agent', data);
    return res.data.data;
  },

  // Code Suggestions & Diffs
  applyApprovedDiff: async (data: { repository_id: string; file_path: string; unified_diff: string; change_id?: string }): Promise<DiffChangeResponse> => {
    const res = await apiClient.post('/code/apply-approved-diff', data);
    return res.data.data;
  },
  suggestCode: async (data: { repository_id: string; file_path: string; instruction: string }): Promise<any> => {
    const res = await apiClient.post('/code/suggest', data);
    return res.data.data;
  },

  // Health
  getHealth: async () => {
    const res = await apiClient.get('/health');
    return res.data;
  },
  getMetrics: async () => {
    const res = await apiClient.get('/metrics');
    return res.data;
  },
};
