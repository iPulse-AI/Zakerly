from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class CategoryModel(BaseModel):
    id: int
    name: str
    created_at: datetime

class BookModel(BaseModel):
    id: Optional[int] = None
    category_id: int
    title: str
    author: Optional[str] = None
    publication_year: Optional[int] = None
    file_hash: str
    file_name: str
    created_at: Optional[datetime] = None

class BookUploadRequest(BaseModel):
    file_content: bytes = Field(..., description="File content as bytes")
    file_name: str = Field(..., description="Original filename")
    mime_type: str = Field(..., description="MIME type of the file")

class BookMetadata(BaseModel):
    subject: str
    category_id: int
    title: str
    author: Optional[str] = None
    publication_year: Optional[int] = None
    file_hash: str
    file_name: str

class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

class ChatSessionModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    book_id: int
    session_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_string(cls, v):
        if isinstance(v, uuid.UUID):
            return str(v)
        return v

class ChatMessageModel(BaseModel):
    id: Optional[int] = None
    session_id: str
    message_type: MessageType
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

class ChatRequest(BaseModel):
    category: str = Field(..., description="Book category")
    book_title: str = Field(..., description="Book title")
    session_id: Optional[str] = Field(default="", description="Chat session ID - empty string for new sessions")
    user_message: str = Field(..., description="User's message")
    intent: Optional[str] = Field(default="answer_question", description="Chat intent")

class ChatResponse(BaseModel):
    response: str
    session_id: str
    intent: str
    metadata: Optional[Dict[str, Any]] = None

class QuestionGenerationRequest(BaseModel):
    book_title: str
    user_message: str
    topics: Optional[List[str]] = None
    count: Optional[int] = 5
    difficulty: Optional[List[str]] = None
    question_types: Optional[List[str]] = None
    scope_type: Optional[str] = "whole_book"  # 'whole_book' or 'specific_topics'
    specific_topics: Optional[str] = None
    time_limit: Optional[int] = None  # in minutes
    category_id: Optional[str] = None

class Question(BaseModel):
    difficulty: str
    type: str
    question_text: str
    options: List[str]
    answer: str

class QuestionResponse(BaseModel):
    chapter: str
    questions_generated: List[Question]

class LectureRequest(BaseModel):
    book_title: str
    user_message: str
    category: Optional[str] = None
    title: Optional[str] = None
    scope: Optional[str] = "whole_book"  # 'whole_book' or 'specific_topics'
    specific_topics: Optional[str] = None
    detail_level: Optional[str] = "overview"  # 'overview', 'detailed', 'in-depth'

class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    service: str
    version: str

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime