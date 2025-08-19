import logging
from typing import List, Optional, Dict, Any
import asyncio
from datetime import datetime
import json

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import sys
sys.path.append('/app/shared')

from models import BookModel, BookMetadata, CategoryModel
from database import DatabaseManager
from utils import calculate_file_hash, sanitize_title_for_table, extract_category_id, RedisManager, validate_file_type
import tempfile
import os
import io

logger = logging.getLogger(__name__)

class IngestionService:
    def __init__(self, db_manager: DatabaseManager, redis_manager: RedisManager):
        self.db = db_manager
        self.redis = redis_manager
        
        # Initialize LangChain components
        self.embeddings = OllamaEmbeddings(
            model='nomic-embed-text:latest',
            base_url=os.getenv("OLLAMA_BASE_URL")
        )
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            temperature=0,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        # Metadata extraction prompt
        self.metadata_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert document analysis and metadata extraction AI. Your sole function is to analyze the provided text and metadata to create a complete, structured JSON record.

Your response MUST be a single, clean JSON object with the following keys: `subject`, `category_id`, `title`, `author`, `publication_year`, `file_hash`, `file_name`.

**INSTRUCTIONS:**

1. **Analyze Text Content:**
   - **Classify** the book's main topic to determine the `subject`. The subject name MUST be from: math, science, physics, chemistry, history, geology, general
   - **Extract** the `title`, `author`, and `publication_year`. If any cannot be found, their value MUST be `null`.

2. **Format the `title` for Database Use:**
   - Convert the entire title to UPPERCASE.
   - Replace all spaces with a single underscore (`_`).
   - Remove any characters that are NOT uppercase letters (A-Z), numbers (0-9), or underscores (`_`).

3. **Use Category ID Mapping:**
   - math: 1, science: 2, physics: 3, chemistry: 4, history: 5, geology: 6, general: 7

4. **Copy from Provided Metadata:**
   - Copy the `file_hash` and `file_name` values directly.

Respond with ONLY the JSON object, no additional text."""),
            ("human", "Text Content: {text}\n\nFile Hash: {file_hash}\nFile Name: {file_name}")
        ])

    async def process_book(self, content: bytes, filename: str, mime_type: str) -> BookModel:
        """Process uploaded book file"""
        try:
            # Validate file type
            if not validate_file_type(mime_type):
                raise ValueError(f"Unsupported file type: {mime_type}")
            
            # Calculate file hash
            file_hash = calculate_file_hash(content)
            
            # Check if book already exists
            if await self.db.check_book_exists(file_hash):
                raise ValueError("Book already exists in the system")
            
            # Extract text from file
            text_content = await self._extract_text(content, filename, mime_type)
            
            # Extract metadata using LLM
            metadata = await self._extract_metadata(text_content, file_hash, filename)
            
            # Insert book into database
            book_id = await self.db.insert_book({
                'category_id': metadata.category_id,
                'title': metadata.title,
                'author': metadata.author,
                'publication_year': metadata.publication_year,
                'file_hash': metadata.file_hash,
                'file_name': metadata.file_name
            })
            
            # Create vector store for the book
            await self._create_vector_store(text_content, metadata.title)
            
            # Create and return book model
            book = BookModel(
                id=book_id,
                category_id=metadata.category_id,
                title=metadata.title,
                author=metadata.author,
                publication_year=metadata.publication_year,
                file_hash=metadata.file_hash,
                file_name=metadata.file_name,
                created_at=datetime.utcnow()
            )
            
            # Cache the book data
            await self._cache_book(book)
            
            logger.info(f"Successfully processed book: {metadata.title}")
            return book
            
        except Exception as e:
            logger.error(f"Error processing book: {e}")
            raise

    async def _extract_text(self, content: bytes, filename: str, mime_type: str) -> str:
        """Extract text from file content"""
        try:
            if mime_type == "application/pdf":
                # Create temporary file for PDF processing
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                    temp_file.write(content)
                    temp_file.flush()
                    
                    # Use PyPDFLoader
                    loader = PyPDFLoader(temp_file.name)
                    documents = loader.load()
                    
                    # Clean up temp file
                    os.unlink(temp_file.name)
                    
                    # Combine all pages
                    text = "\n".join([doc.page_content for doc in documents])
                    
            elif mime_type == "text/plain":
                text = content.decode('utf-8')
                
            else:
                # For other formats, try to decode as text
                text = content.decode('utf-8', errors='ignore')
            
            # Return full text for processing, but log length
            logger.info(f"Extracted text length: {len(text)} characters")
            return text
            
        except Exception as e:
            logger.error(f"Error extracting text from {filename}: {e}")
            raise ValueError(f"Failed to extract text from file: {e}")

    async def _extract_metadata(self, text: str, file_hash: str, filename: str) -> BookMetadata:
        """Extract metadata using LLM"""
        result = ""
        try:
            # Create chain
            chain = self.metadata_prompt | self.llm | StrOutputParser()
            
            # Run extraction with limited text for LLM
            text_for_llm = text[:8000] if len(text) > 8000 else text
            result = await chain.ainvoke({
                "text": text_for_llm,
                "file_hash": file_hash,
                "file_name": filename
            })
            
            # Clean and validate the result
            result = result.strip()
            if not result:
                logger.warning("Empty response from LLM, using fallback metadata")
                raise ValueError("Empty response from LLM")
            
            # Try to extract JSON from the response if it contains extra text
            if result.startswith('```json'):
                result = result.replace('```json', '').replace('```', '').strip()
            elif result.startswith('```'):
                result = result.replace('```', '').strip()
            
            # Find JSON object in the response
            start_idx = result.find('{')
            end_idx = result.rfind('}')
            if start_idx != -1 and end_idx != -1:
                result = result[start_idx:end_idx+1]
            else:
                logger.warning("No valid JSON found in LLM response, using fallback metadata")
                raise ValueError("No valid JSON found in response")
            
            # Parse JSON response
            try:
                metadata_dict = json.loads(result)
            except json.JSONDecodeError as json_error:
                logger.warning(f"JSON decode error: {json_error}, using fallback metadata")
                raise ValueError(f"Invalid JSON: {json_error}")
            
            # Validate required fields
            required_fields = ['subject', 'category_id', 'title', 'file_hash', 'file_name']
            for field in required_fields:
                if field not in metadata_dict:
                    logger.warning(f"Missing required field: {field}, using fallback metadata")
                    raise ValueError(f"Missing required field: {field}")
            
            # Create BookMetadata object
            metadata = BookMetadata(
                subject=metadata_dict['subject'],
                category_id=metadata_dict['category_id'],
                title=metadata_dict['title'],
                author=metadata_dict.get('author'),
                publication_year=metadata_dict.get('publication_year'),
                file_hash=metadata_dict['file_hash'],
                file_name=metadata_dict['file_name']
            )
            
            logger.info(f"Successfully extracted metadata for: {metadata.title}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            logger.error(f"LLM response was: {result if result else 'No response'}")
            
            # Determine subject from filename for physics book
            subject = "physics" if "physics" in filename.lower() else "general"
            category_id = 3 if subject == "physics" else 7
            
            # Fallback to basic metadata
            fallback_metadata = BookMetadata(
                subject=subject,
                category_id=category_id,
                title=sanitize_title_for_table(filename.split('.')[0]),
                author=None,
                publication_year=None,
                file_hash=file_hash,
                file_name=filename
            )
            
            logger.info(f"Using fallback metadata: {fallback_metadata.title}")
            return fallback_metadata

    async def _create_vector_store(self, text: str, table_name: str):
        """Create vector store for the book"""
        try:
            # Split text into chunks
            documents = self.text_splitter.create_documents([text])
            
            # Create embeddings for all documents
            texts = [doc.page_content for doc in documents]
            embeddings_list = await self.embeddings.aembed_documents(texts)
            
            # Determine embedding dimension from first embedding
            if not embeddings_list:
                raise ValueError("No embeddings generated")
            
            embedding_dim = len(embeddings_list[0])
            logger.info(f"Embedding dimension: {embedding_dim}")
            
            # Create table and insert vectors directly
            connection_string = os.getenv("DATABASE_URL")
            
            # Use asyncpg to create table and insert data
            import asyncpg
            conn = await asyncpg.connect(connection_string)
            
            try:
                # Create table with pgvector extension using actual embedding dimension
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id SERIAL PRIMARY KEY,
                        content TEXT,
                        metadata JSONB,
                        embedding vector({embedding_dim})
                    )
                """)
                
                # Insert documents with embeddings
                for i, (doc, embedding) in enumerate(zip(documents, embeddings_list)):
                    try:
                        # Ensure embedding is a list of floats
                        if not isinstance(embedding, list):
                            embedding = list(embedding)
                        
                        # Convert embedding to string format for PostgreSQL vector
                        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                        
                        # Insert with proper vector format
                        await conn.execute(f"""
                            INSERT INTO {table_name} (content, metadata, embedding)
                            VALUES ($1, $2, $3::vector)
                        """, doc.page_content, json.dumps(doc.metadata), embedding_str)
                    except Exception as insert_error:
                        logger.error(f"Error inserting chunk {i}: {insert_error}")
                        logger.error(f"Embedding length: {len(embedding)}")
                        logger.error(f"Embedding type: {type(embedding)}")
                        logger.error(f"First few embedding values: {embedding[:5] if len(embedding) > 5 else embedding}")
                        raise
                
                logger.info(f"Created vector store table {table_name} with {len(documents)} chunks")
                
            finally:
                await conn.close()
            
        except Exception as e:
            logger.error(f"Error creating vector store for {table_name}: {e}")
            raise

    async def _cache_book(self, book: BookModel):
        """Cache book data in Redis"""
        try:
            cache_key = f"book:{book.id}"
            book_data = book.dict()
            book_data['created_at'] = book_data['created_at'].isoformat() if book_data['created_at'] else None
            
            self.redis.set_cache(cache_key, book_data, expire_seconds=3600)
            
        except Exception as e:
            logger.warning(f"Failed to cache book data: {e}")

    async def list_books(self, category_id: int = None) -> List[BookModel]:
        """List books, optionally filtered by category"""
        try:
            if category_id:
                books_data = await self.db.get_books_by_category(category_id)
            else:
                books_data = await self.db.execute_query(
                    "SELECT * FROM books ORDER BY created_at DESC"
                )
            
            books = []
            for book_data in books_data:
                book = BookModel(**book_data)
                books.append(book)
            
            return books
            
        except Exception as e:
            logger.error(f"Error listing books: {e}")
            raise

    async def list_categories(self) -> List[CategoryModel]:
        """List all categories"""
        try:
            categories_data = await self.db.get_categories()
            categories = [CategoryModel(**cat_data) for cat_data in categories_data]
            return categories
            
        except Exception as e:
            logger.error(f"Error listing categories: {e}")
            raise

    async def get_book_by_id(self, book_id: int) -> Optional[BookModel]:
        """Get book by ID"""
        try:
            # Try cache first
            cache_key = f"book:{book_id}"
            cached_data = self.redis.get_cache(cache_key)
            
            if cached_data:
                if cached_data.get('created_at'):
                    cached_data['created_at'] = datetime.fromisoformat(cached_data['created_at'])
                return BookModel(**cached_data)
            
            # Get from database
            book_data = await self.db.fetch_one(
                "SELECT * FROM books WHERE id = $1", book_id
            )
            
            if book_data:
                book = BookModel(**book_data)
                await self._cache_book(book)
                return book
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting book {book_id}: {e}")
            raise

    async def delete_book(self, book_id: int) -> bool:
        """Delete book and its vector store"""
        try:
            # Get book info first
            book = await self.get_book_by_id(book_id)
            if not book:
                return False
            
            # Delete from vector store (drop table)
            try:
                # Drop the table with the book title name
                await self.db.execute_command(f"DROP TABLE IF EXISTS {book.title}")
            except Exception as e:
                logger.warning(f"Failed to drop vector table for {book.title}: {e}")
            
            # Delete from books table
            result = await self.db.execute_command(
                "DELETE FROM books WHERE id = $1", book_id
            )
            
            # Remove from cache
            cache_key = f"book:{book_id}"
            self.redis.delete_cache(cache_key)
            
            return "DELETE 1" in result
            
        except Exception as e:
            logger.error(f"Error deleting book {book_id}: {e}")
            raise