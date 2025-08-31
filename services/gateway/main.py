from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import httpx
import os
import sys
from datetime import datetime
import logging
from contextlib import asynccontextmanager
import json
from fastapi import Response

# Add shared modules to path
sys.path.append('/app/shared')

from models import (
    ChatRequest, ChatResponse, QuestionGenerationRequest, 
    LectureRequest, HealthCheck, BookModel
)
from utils import setup_logging, get_redis

# Setup logging
setup_logging("api-gateway")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting API Gateway...")
    
    # Initialize Redis for rate limiting and caching
    redis_manager = get_redis()
    app.state.redis = redis_manager
    
    # Increase HTTP client timeout for file uploads and long operations
    app.state.http_client = httpx.AsyncClient(timeout=httpx.Timeout(10000.0))  # 30 minutes timeout
    app.state.rate_limiter = RateLimiter(app.state.redis)
    
    logger.info("API Gateway started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down API Gateway...")
    await app.state.http_client.aclose()
    redis_manager.disconnect()

app = FastAPI(
    title="Zakerly API Gateway",
    description="API Gateway for Zakerly microservices platform",
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

# Service URLs
INGESTION_SERVICE_URL = os.getenv("INGESTION_SERVICE_URL", "http://ingestion-service:8000")
CHAT_SERVICE_URL = os.getenv("CHAT_SERVICE_URL", "http://chat-service:8000")

class RateLimiter:
    """Simple rate limiter using Redis"""
    
    def __init__(self, redis_manager, max_requests: int = 100, window_seconds: int = 60):
        self.redis = redis_manager
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed"""
        try:
            if not self.redis.client:
                return True  # Allow if Redis is not available
            
            key = f"rate_limit:{client_id}"
            current = self.redis.client.get(key)
            
            if current is None:
                # First request in window
                self.redis.client.setex(key, self.window_seconds, 1)
                return True
            
            if int(current) >= self.max_requests:
                return False
            
            # Increment counter
            self.redis.client.incr(key)
            return True
            
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            return True  # Allow on error

async def check_rate_limit(request: Request):
    """Rate limiting dependency"""
    client_ip = request.client.host
    
    if not await request.app.state.rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )

async def forward_request(
    service_url: str,
    endpoint: str,
    method: str = "GET",
    data: dict = None,
    files: dict = None,
    params: dict = None
) -> dict:
    """Forward request to microservice"""
    try:
        url = f"{service_url}{endpoint}"
        
        client = app.state.http_client
        if method == "GET":
            response = await client.get(url, params=params)
        elif method == "POST":
            if files:
                response = await client.post(url, files=files, data=data, params=params)
            else:
                response = await client.post(url, json=data, params=params)
        elif method == "DELETE":
            response = await client.delete(url)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error forwarding to {service_url}{endpoint}: {e}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Service error: {e.response.text}"
        )
    except Exception as e:
        logger.error(f"Error forwarding to {service_url}{endpoint}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Gateway error: {str(e)}"
        )


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    return HealthCheck(
        status="healthy",
        timestamp=datetime.utcnow(),
        service="api-gateway",
        version="1.0.0"
    )

# Ingestion Service Endpoints
@app.post("/api/v1/upload", response_model=BookModel, dependencies=[Depends(check_rate_limit)])
async def upload_book(file: UploadFile = File(...)):
    """Upload book file"""
    try:
        # Prepare file for forwarding
        file_content = await file.read()
        files = {"file": (file.filename, file_content, file.content_type)}
        
        result = await forward_request(
            INGESTION_SERVICE_URL,
            "/upload",
            method="POST",
            files=files
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in upload endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/books", dependencies=[Depends(check_rate_limit)])
async def list_books(category_id: int = None):
    """List books"""
    try:
        params = {"category_id": category_id} if category_id else None
        result = await forward_request(
            INGESTION_SERVICE_URL,
            "/books",
            method="GET",
            params=params
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list books endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/categories", dependencies=[Depends(check_rate_limit)])
async def list_categories():
    """List categories"""
    try:
        result = await forward_request(
            INGESTION_SERVICE_URL,
            "/categories",
            method="GET"
        )
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list categories endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/books/{book_id}", dependencies=[Depends(check_rate_limit)])
async def get_book(book_id: int):
    """Get book by ID"""
    try:
        result = await forward_request(
            INGESTION_SERVICE_URL,
            f"/books/{book_id}",
            method="GET"
        )
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get book endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/books/{book_id}", dependencies=[Depends(check_rate_limit)])
async def delete_book(book_id: int):
    """Delete book"""
    try:
        result = await forward_request(
            INGESTION_SERVICE_URL,
            f"/books/{book_id}",
            method="DELETE"
        )
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete book endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Chat Service Endpoints
@app.post("/api/v1/chat", response_model=ChatResponse, dependencies=[Depends(check_rate_limit)])
async def chat(request: ChatRequest):
    """Handle chat request"""
    try:
        result = await forward_request(
            CHAT_SERVICE_URL,
            "/chat",
            method="POST",
            data=request.dict()
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/generate-questions", dependencies=[Depends(check_rate_limit)])
async def generate_questions(request: QuestionGenerationRequest):
    """Generate questions"""
    try:
        result = await forward_request(
            CHAT_SERVICE_URL,
            "/generate-questions",
            method="POST",
            data=request.dict()
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate questions endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/generate-lecture", dependencies=[Depends(check_rate_limit)])
async def generate_lecture(request: LectureRequest):
    """Generate lecture"""
    try:
        result = await forward_request(
            CHAT_SERVICE_URL,
            "/generate-lecture",
            method="POST",
            data=request.dict()
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate lecture endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Session Management Endpoints
@app.post("/api/v1/sessions", dependencies=[Depends(check_rate_limit)])
async def create_session(user_id: str, book_title: str, session_name: str = None):
    """Create chat session"""
    try:
        # Pass as query parameters to match chat service expectation
        params = {
            "user_id": user_id,
            "book_title": book_title
        }
        if session_name:
            params["session_name"] = session_name
        
        result = await forward_request(
            CHAT_SERVICE_URL,
            "/sessions",
            method="POST",
            params=params
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create session endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sessions/{session_id}", dependencies=[Depends(check_rate_limit)])
async def get_session(session_id: str):
    """Get session"""
    try:
        result = await forward_request(
            CHAT_SERVICE_URL,
            f"/sessions/{session_id}",
            method="GET"
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get session endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/users/{user_id}/sessions", dependencies=[Depends(check_rate_limit)])
async def get_user_sessions(user_id: str):
    """Get user sessions"""
    try:
        result = await forward_request(
            CHAT_SERVICE_URL,
            f"/users/{user_id}/sessions",
            method="GET"
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get user sessions endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sessions/{session_id}/history", dependencies=[Depends(check_rate_limit)])
async def get_chat_history(session_id: str, limit: int = 50):
    """Get chat history"""
    try:
        params = {"limit": limit}
        result = await forward_request(
            CHAT_SERVICE_URL,
            f"/sessions/{session_id}/history",
            method="GET",
            params=params
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get chat history endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/sessions/{session_id}", dependencies=[Depends(check_rate_limit)])
async def delete_session(session_id: str):
    """Delete session"""
    try:
        result = await forward_request(
            CHAT_SERVICE_URL,
            f"/sessions/{session_id}",
            method="DELETE"
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete session endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/status")
async def get_system_status():
    """Get system status"""
    try:
        status = {
            "gateway": "healthy",
            "services": {}
        }
        
        # Check ingestion service
        try:
            await forward_request(INGESTION_SERVICE_URL, "/health", method="GET")
            status["services"]["ingestion"] = "healthy"
        except:
            status["services"]["ingestion"] = "unhealthy"
        
        # Check chat service
        try:
            await forward_request(CHAT_SERVICE_URL, "/health", method="GET")
            status["services"]["chat"] = "healthy"
        except:
            status["services"]["chat"] = "unhealthy"
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url)
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )