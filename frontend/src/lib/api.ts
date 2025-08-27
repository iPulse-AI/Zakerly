// API configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// API endpoints
export const API_ENDPOINTS = {
  // Books & Ingestion
  UPLOAD_BOOK: '/api/v1/upload',
  BOOKS: '/api/v1/books',
  CATEGORIES: '/api/v1/categories',
  BOOK_BY_ID: (id: number) => `/api/v1/books/${id}`,
  DELETE_BOOK: (id: number) => `/api/v1/books/${id}`,
  
  // Chat
  CHAT: '/api/v1/chat',
  GENERATE_QUESTIONS: '/api/v1/generate-questions',
  GENERATE_LECTURE: '/api/v1/generate-lecture',
  
  // Sessions
  SESSIONS: '/api/v1/sessions',
  SESSION_BY_ID: (id: string) => `/api/v1/sessions/${id}`,
  USER_SESSIONS: (userId: string) => `/api/v1/users/${userId}/sessions`,
  CHAT_HISTORY: (sessionId: string) => `/api/v1/sessions/${sessionId}/history`,
  DELETE_SESSION: (sessionId: string) => `/api/v1/sessions/${sessionId}`,
  
  // System
  HEALTH: '/health',
  STATUS: '/api/v1/status'
};

// Generic API client
class ApiClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private async request<T>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async postFormData<T>(endpoint: string, formData: FormData): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
}

export const apiClient = new ApiClient(API_BASE_URL);
