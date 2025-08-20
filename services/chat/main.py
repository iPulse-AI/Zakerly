from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys
from datetime import datetime
import logging
from contextlib import asynccontextmanager

# Add shared modules to path
sys.path.append('/app/shared')

from models import (
    ChatRequest, ChatResponse, QuestionGenerationRequest, QuestionResponse,
    LectureRequest, HealthCheck, ChatSessionModel
)
from database import get_database, DatabaseManager
from utils import setup_logging, get_redis, metrics, generate_session_id
from chat_service import ChatService

# Setup logging
setup_logging("chat-service")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Chat Service...")
    
    # Initialize database
    db = get_database()
    await db.initialize()
    
    # Initialize Redis
    redis_manager = get_redis()
    
    # Initialize chat service
    app.state.chat_service = ChatService(db, redis_manager)
    
    logger.info("Chat Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Chat Service...")
    await db.close()
    redis_manager.disconnect()

app = FastAPI(
    title="Zakerly Chat Service",
    description="Intelligent chat service for Zakerly platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_chat_service() -> ChatService:
    """Dependency to get chat service"""
    return app.state.chat_service

@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    return HealthCheck(
        status="healthy",
        timestamp=datetime.utcnow(),
        service="chat-service",
        version="1.0.0"
    )

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Handle chat requests"""
    try:
        # Record metrics
        metrics.increment_counter("chat_requests", {
            "service": "chat",
            "intent": request.intent or "answer_question"
        })
        
        logger.info(f"Chat request for book: {request.book_title}, session: {request.session_id}")
        
        response = await chat_service.handle_chat(request)
        
        metrics.increment_counter("chat_responses", {
            "service": "chat",
            "intent": response.intent
        })
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_counter("chat_errors", {"service": "chat"})
        logger.error(f"Error handling chat request: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/generate-questions", response_model=QuestionResponse)
async def generate_questions(
    request: QuestionGenerationRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Generate questions for a book"""
    try:
        metrics.increment_counter("question_generation_requests", {"service": "chat"})
        
        logger.info(f"Question generation request for book: {request.book_title}")
        
        response = await chat_service.generate_questions(request)
        
        metrics.increment_counter("question_generation_success", {"service": "chat"})
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_counter("question_generation_errors", {"service": "chat"})
        logger.error(f"Error generating questions: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/generate-lecture")
async def generate_lecture(
    request: LectureRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Generate lecture for a book topic"""
    try:
        metrics.increment_counter("lecture_generation_requests", {"service": "chat"})
        
        logger.info(f"Lecture generation request for book: {request.book_title}")
        
        response = await chat_service.generate_lecture(request)
        
        metrics.increment_counter("lecture_generation_success", {"service": "chat"})
        
        return {"lecture": response}
        
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_counter("lecture_generation_errors", {"service": "chat"})
        logger.error(f"Error generating lecture: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/sessions", response_model=ChatSessionModel)
async def create_session(
    user_id: str,
    book_title: str,
    session_name: str = None,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Create new chat session"""
    try:
        session = await chat_service.create_session(user_id, book_title, session_name)
        return session
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/sessions/{session_id}", response_model=ChatSessionModel)
async def get_session(
    session_id: str,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get chat session by ID"""
    try:
        session = await chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/users/{user_id}/sessions", response_model=list[ChatSessionModel])
async def get_user_sessions(
    user_id: str,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get all sessions for a user"""
    try:
        sessions = await chat_service.get_user_sessions(user_id)
        return sessions
        
    except Exception as e:
        logger.error(f"Error getting user sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/sessions/{session_id}/history")
async def get_chat_history(
    session_id: str,
    limit: int = 50,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get chat history for session"""
    try:
        history = await chat_service.get_chat_history(session_id, limit)
        return {"history": history}
        
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Delete chat session"""
    try:
        success = await chat_service.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Session deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Memory management endpoints
@app.get("/memory/stats/{session_id}")
async def get_memory_stats(
    session_id: str,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get memory statistics for a session"""
    try:
        stats = await chat_service.get_memory_stats(session_id)
        return stats
    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/memory/entities/{session_id}")
async def get_session_entities(
    session_id: str,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get extracted entities for a session"""
    try:
        entities = await chat_service.get_session_entities(session_id)
        return entities
    except Exception as e:
        logger.error(f"Error getting session entities: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/memory/summary/{session_id}")
async def get_session_summary(
    session_id: str,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Get conversation summary for a session"""
    try:
        summary = await chat_service.get_session_summary(session_id)
        return summary
    except Exception as e:
        logger.error(f"Error getting session summary: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.delete("/memory/clear/{session_id}")
async def clear_session_memory(
    session_id: str,
    chat_service: ChatService = Depends(get_chat_service)
):
    """Clear memory for a specific session"""
    try:
        success = await chat_service.clear_session_memory(session_id)
        if success:
            return {"message": "Session memory cleared successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear session memory")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing session memory: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/memory/cleanup")
async def cleanup_expired_memories(
    chat_service: ChatService = Depends(get_chat_service)
):
    """Clean up expired memories across all sessions"""
    try:
        result = await chat_service.cleanup_expired_memories()
        return result
    except Exception as e:
        logger.error(f"Error cleaning up expired memories: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/metrics")
async def get_metrics():
    """Get service metrics"""
    # This would integrate with Prometheus in a real implementation
    return {"message": "Metrics endpoint - integrate with Prometheus"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )