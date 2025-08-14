from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys
from datetime import datetime
import logging
from contextlib import asynccontextmanager

# Add shared modules to path
sys.path.append('/app/shared')

from models import BookModel, BookMetadata, HealthCheck, ErrorResponse
from database import get_database, DatabaseManager
from utils import setup_logging, get_redis, metrics
from ingestion_service import IngestionService

# Setup logging
setup_logging("ingestion-service")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Ingestion Service...")
    
    # Initialize database
    db = get_database()
    await db.initialize()
    
    # Initialize Redis
    redis_manager = get_redis()
    
    # Initialize ingestion service
    app.state.ingestion_service = IngestionService(db, redis_manager)
    
    logger.info("Ingestion Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Ingestion Service...")
    await db.close()
    redis_manager.disconnect()

app = FastAPI(
    title="Zakerly Ingestion Service",
    description="Document ingestion and processing service for Zakerly platform",
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

def get_ingestion_service() -> IngestionService:
    """Dependency to get ingestion service"""
    return app.state.ingestion_service

@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    return HealthCheck(
        status="healthy",
        timestamp=datetime.utcnow(),
        service="ingestion-service",
        version="1.0.0"
    )

@app.post("/upload", response_model=BookModel)
async def upload_book(
    file: UploadFile = File(...),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    """Upload and process a book file"""
    try:
        # Record metrics
        metrics.increment_counter("book_upload_requests", {"service": "ingestion"})
        
        logger.info(f"Received file upload: {file.filename}")
        
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Read file content
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Process the book
        book = await ingestion_service.process_book(
            content=content,
            filename=file.filename,
            mime_type=file.content_type or "application/octet-stream"
        )
        
        metrics.increment_counter("book_upload_success", {"service": "ingestion"})
        logger.info(f"Successfully processed book: {book.title}")
        
        return book
        
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_counter("book_upload_errors", {"service": "ingestion"})
        logger.error(f"Error processing book upload: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/books", response_model=list[BookModel])
async def list_books(
    category_id: int = None,
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    """List all books or books by category"""
    try:
        books = await ingestion_service.list_books(category_id)
        return books
    except Exception as e:
        logger.error(f"Error listing books: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/categories")
async def list_categories(
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    """List all categories"""
    try:
        categories = await ingestion_service.list_categories()
        return categories
    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/books/{book_id}", response_model=BookModel)
async def get_book(
    book_id: int,
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    """Get book by ID"""
    try:
        book = await ingestion_service.get_book_by_id(book_id)
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        return book
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting book {book_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.delete("/books/{book_id}")
async def delete_book(
    book_id: int,
    ingestion_service: IngestionService = Depends(get_ingestion_service)
):
    """Delete book by ID"""
    try:
        success = await ingestion_service.delete_book(book_id)
        if not success:
            raise HTTPException(status_code=404, detail="Book not found")
        return {"message": "Book deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting book {book_id}: {e}")
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