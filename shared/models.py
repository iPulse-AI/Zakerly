from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class CurriculumModel(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_by: str = 'system'
    created_at: datetime
    updated_at: datetime

class BookModel(BaseModel):
    id: Optional[int] = None
    curriculum_id: int
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
    curriculum_id: Optional[int] = Field(None, description="Curriculum ID - required for new system")
    curriculum_name: Optional[str] = Field(None, description="Curriculum name - for creating new curriculum")

class BookMetadata(BaseModel):
    curriculum_id: int
    curriculum_name: str
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
    curriculum: str = Field(..., description="Curriculum name (required)")
    session_id: Optional[str] = Field(default="", description="Chat session ID - empty string for new sessions")
    user_message: str = Field(..., description="User's message")
    intent: Optional[str] = Field(default="answer_question", description="Chat intent")

class ChatResponse(BaseModel):
    response: str
    session_id: str
    intent: str
    metadata: Optional[Dict[str, Any]] = None

class QuestionGenerationRequest(BaseModel):
    curriculum: Optional[str] = Field(None, description="Curriculum name")
    book_title: Optional[str] = Field(None, description="Specific book title")
    curriculum_id: Optional[str] = Field(None, description="Curriculum ID")
    user_message: str
    topics: Optional[List[str]] = None
    count: Optional[int] = 5
    difficulty: Optional[List[str]] = None
    question_types: Optional[List[str]] = None
    scope_type: Optional[str] = "whole_book"  # 'whole_curriculum', 'whole_book' or 'specific_topics'
    specific_topics: Optional[str] = None
    time_limit: Optional[int] = None  # in minutes

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
    curriculum: str = Field(..., description="Curriculum name (required)")
    user_message: str
    title: Optional[str] = None
    scope: Optional[str] = "whole_book"  # 'whole_book' or 'specific_topics'
    specific_topics: Optional[str] = None
    detail_level: Optional[str] = "overview"  # 'overview', 'detailed', 'in-depth'

class LectureScript(BaseModel):
    id: Optional[str] = None
    user_id: str
    book_id: int
    title: str
    scope: str = Field(..., description="Scope: whole_book or specific_topics")
    specific_topics: Optional[str] = None
    detail_level: str = Field(..., description="Detail level: overview, detailed, or in-depth")
    difficulty: str = Field(..., description="Difficulty: beginner, intermediate, or advanced")
    duration: int = Field(..., description="Duration in minutes")
    content: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @field_validator('id', mode='before')
    @classmethod
    def convert_uuid_to_string(cls, v):
        if isinstance(v, uuid.UUID):
            return str(v)
        return v
    
    @field_validator('user_id', mode='before')
    @classmethod
    def convert_user_id_to_string(cls, v):
        if isinstance(v, uuid.UUID):
            return str(v)
        return v

class LectureScriptRequest(BaseModel):
    book_id: int
    title: str
    scope: str = Field(..., description="Scope: whole_book or specific_topics")
    specific_topics: Optional[str] = None
    detail_level: str = Field(..., description="Detail level: overview, detailed, or in-depth")
    difficulty: str = Field(..., description="Difficulty: beginner, intermediate, or advanced")
    duration: int = Field(..., description="Duration in minutes")
    content: str

class LectureScriptUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    scope: Optional[str] = None
    specific_topics: Optional[str] = None
    detail_level: Optional[str] = None
    difficulty: Optional[str] = None
    duration: Optional[int] = None

# Curriculum-specific models
class CurriculumCreateRequest(BaseModel):
    name: str = Field(..., description="Curriculum name")
    description: Optional[str] = Field(None, description="Curriculum description")
    created_by: str = Field('user', description="Who created this curriculum")

class CurriculumUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, description="Curriculum name")
    description: Optional[str] = Field(None, description="Curriculum description")

class BookWithCurriculum(BaseModel):
    id: int
    curriculum_id: int
    curriculum_name: str
    title: str
    author: Optional[str] = None
    publication_year: Optional[int] = None
    file_hash: str
    file_name: str
    created_at: datetime

class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    service: str
    version: str

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime