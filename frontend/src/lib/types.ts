// Core data types matching backend models

export interface Category {
  id: number;
  name: string;
  created_at: string;
}

export interface Book {
  id: number;
  category_id: number;
  title: string;
  author: string | null;
  publication_year: number | null;
  file_hash: string;
  file_name: string;
  created_at: string;
}

export interface BookWithCategory extends Book {
  category_name?: string;
}

export interface ChatSession {
  id: string;
  user_id: string;
  book_id: number;
  session_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatMessage {
  id: number;
  session_id: string;
  message_type: 'user' | 'assistant';
  content: string;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface ChatRequest {
  category: string;
  book_title: string;
  session_id: string;
  user_message: string;
  intent?: string;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  intent: string;
  metadata?: Record<string, any>;
}

export interface QuestionGenerationRequest {
  book_title: string;
  user_message: string;
  topics?: string[];
  count?: number;
  difficulty?: string[];
  question_types?: string[];
}

export interface Question {
  difficulty: string;
  type: string;
  question_text: string;
  options: string[];
  answer: string;
}

export interface QuestionResponse {
  chapter: string;
  questions_generated: Question[];
}

export interface LectureRequest {
  book_title: string;
  topic?: string;
  audience?: string;
}

// Upload types
export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

// Error types
export interface ApiError {
  error: string;
  detail?: string;
  timestamp: string;
}

// System status
export interface SystemStatus {
  gateway: string;
  services: {
    ingestion: string;
    chat: string;
  };
}

// Local storage types for frontend state
export interface LocalBook extends Book {
  progress?: number;
  status?: 'reading' | 'completed' | 'not-started';
  last_read?: string;
}

// Category mapping (matching backend)
export const CATEGORY_MAP = {
  1: 'math',
  2: 'science', 
  3: 'physics',
  4: 'chemistry',
  5: 'history',
  6: 'geology',
  7: 'general'
} as const;

export const CATEGORY_NAMES = {
  math: 'Mathematics',
  science: 'Science',
  physics: 'Physics', 
  chemistry: 'Chemistry',
  history: 'History',
  geology: 'Geology',
  general: 'General'
} as const;
