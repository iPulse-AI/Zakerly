import { apiClient, API_ENDPOINTS } from './api';
import type {
  Book,
  Category,
  ChatRequest,
  ChatResponse,
  QuestionGenerationRequest,
  QuestionResponse,
  LectureRequest,
  ChatSession,
  ChatMessage,
  SystemStatus,
  UploadProgress
} from './types';

// Books & Categories Service
export class BooksService {
  static async uploadBook(
    file: File,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<Book> {
    const formData = new FormData();
    formData.append('file', file);

    // For progress tracking, we'd need to use XMLHttpRequest
    // For now, using the simpler fetch approach
    return apiClient.postFormData<Book>(API_ENDPOINTS.UPLOAD_BOOK, formData);
  }

  static async getBooks(categoryId?: number): Promise<Book[]> {
    const endpoint = categoryId 
      ? `${API_ENDPOINTS.BOOKS}?category_id=${categoryId}`
      : API_ENDPOINTS.BOOKS;
    return apiClient.get<Book[]>(endpoint);
  }

  static async getBookById(id: number): Promise<Book> {
    return apiClient.get<Book>(API_ENDPOINTS.BOOK_BY_ID(id));
  }

  static async deleteBook(id: number): Promise<{ message: string }> {
    return apiClient.delete<{ message: string }>(API_ENDPOINTS.DELETE_BOOK(id));
  }

  static async getCategories(): Promise<Category[]> {
    return apiClient.get<Category[]>(API_ENDPOINTS.CATEGORIES);
  }
}

// Chat Service
export class ChatService {
  static async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    return apiClient.post<ChatResponse>(API_ENDPOINTS.CHAT, request);
  }

  static async generateQuestions(request: QuestionGenerationRequest): Promise<QuestionResponse> {
    return apiClient.post<QuestionResponse>(API_ENDPOINTS.GENERATE_QUESTIONS, request);
  }

  static async generateLecture(request: LectureRequest): Promise<{ lecture: string }> {
    return apiClient.post<{ lecture: string }>(API_ENDPOINTS.GENERATE_LECTURE, request);
  }
}

// Session Management Service
export class SessionService {
  static async createSession(
    userId: string,
    bookTitle: string,
    sessionName?: string
  ): Promise<ChatSession> {
    // Build query parameters to match FastAPI endpoint signature
    const params = new URLSearchParams();
    params.append('user_id', userId);
    params.append('book_title', bookTitle);
    if (sessionName) {
      params.append('session_name', sessionName);
    }
    
    // Send as query parameters in URL
    const endpoint = `${API_ENDPOINTS.SESSIONS}?${params.toString()}`;
    return apiClient.post<ChatSession>(endpoint, {});
  }

  static async getSession(sessionId: string): Promise<ChatSession> {
    return apiClient.get<ChatSession>(API_ENDPOINTS.SESSION_BY_ID(sessionId));
  }

  static async getUserSessions(userId: string): Promise<ChatSession[]> {
    return apiClient.get<ChatSession[]>(API_ENDPOINTS.USER_SESSIONS(userId));
  }

  static async getChatHistory(sessionId: string, limit = 50): Promise<{ history: ChatMessage[] }> {
    const endpoint = `${API_ENDPOINTS.CHAT_HISTORY(sessionId)}?limit=${limit}`;
    return apiClient.get<{ history: ChatMessage[] }>(endpoint);
  }

  static async deleteSession(sessionId: string): Promise<{ message: string }> {
    return apiClient.delete<{ message: string }>(API_ENDPOINTS.DELETE_SESSION(sessionId));
  }
}

// System Service
export class SystemService {
  static async getHealth(): Promise<any> {
    return apiClient.get(API_ENDPOINTS.HEALTH);
  }

  static async getStatus(): Promise<SystemStatus> {
    return apiClient.get<SystemStatus>(API_ENDPOINTS.STATUS);
  }
}

// Utility functions
export class Utils {
  static generateUserId(): string {
    // Generate a simple user ID for now
    let userId = localStorage.getItem('zakerly_user_id');
    if (!userId) {
      userId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem('zakerly_user_id', userId);
    }
    return userId;
  }

  static getCategoryName(categoryId: number): string {
    const categoryMap: Record<number, string> = {
      1: 'Mathematics',
      2: 'Science',
      3: 'Physics',
      4: 'Chemistry',
      5: 'History',
      6: 'Geology',
      7: 'General'
    };
    return categoryMap[categoryId] || 'Unknown';
  }

  static formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  static getFileExtension(filename: string): string {
    return filename.slice((filename.lastIndexOf('.') - 1 >>> 0) + 2);
  }

  static validateFileType(file: File): { valid: boolean; error?: string } {
    const allowedTypes = ['application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    const allowedExtensions = ['pdf', 'txt', 'docx'];
    
    const extension = this.getFileExtension(file.name).toLowerCase();
    
    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(extension)) {
      return {
        valid: false,
        error: 'Only PDF, TXT, and DOCX files are supported'
      };
    }
    
    const maxSize = 100 * 1024 * 1024; // 100MB
    if (file.size > maxSize) {
      return {
        valid: false,
        error: 'File size must be less than 100MB'
      };
    }
    
    return { valid: true };
  }
}
