// Core data types matching backend models

export interface Curriculum {
  id: number;
  name: string;
  description?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface CurriculumCreateRequest {
  name: string;
  description?: string;
  created_by: string;
}

export interface Book {
  id: number;
  curriculum_id: number;
  title: string;
  author: string | null;
  publication_year: number | null;
  file_hash: string;
  file_name: string;
  created_at: string;
}

export interface BookWithCurriculum extends Book {
  curriculum_name?: string;
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
  curriculum: string;
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
  book_title?: string;
  curriculum_id?: string;
  user_message: string;
  topics?: string[];
  count?: number;
  difficulty?: string[];
  question_types?: string[];
  scope_type?: 'whole_curriculum' | 'whole_book' | 'specific_topics';
  specific_topics?: string;
  time_limit?: number;
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
  user_message: string;
  curriculum?: string;
  title?: string;
  scope?: 'whole_book' | 'specific_topics';
  specific_topics?: string;
  detail_level?: 'overview' | 'detailed' | 'in-depth';
}

export interface LectureScript {
  id: string;
  user_id: string;
  book_id: number;
  title: string;
  scope: 'whole_book' | 'specific_topics';
  specific_topics?: string;
  detail_level: 'overview' | 'detailed' | 'in-depth';
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  duration: number; // minutes
  content: string;
  created_at: string;
  updated_at: string;
  book_title?: string; // Added by join query
}

export interface LectureScriptRequest {
  book_id: number;
  title: string;
  scope: 'whole_book' | 'specific_topics';
  specific_topics?: string;
  detail_level: 'overview' | 'detailed' | 'in-depth';
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  duration: number;
  content: string;
}

export interface LectureScriptUpdate {
  title?: string;
  content?: string;
  scope?: 'whole_book' | 'specific_topics';
  specific_topics?: string;
  detail_level?: 'overview' | 'detailed' | 'in-depth';
  difficulty?: 'beginner' | 'intermediate' | 'advanced';
  duration?: number;
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


