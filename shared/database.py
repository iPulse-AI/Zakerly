import asyncpg
import os
from typing import Optional, List, Dict, Any
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool"""
        if not self.pool:
            raise RuntimeError("Database pool not initialized")
        
        async with self.pool.acquire() as connection:
            yield connection

    async def execute_query(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results"""
        async with self.get_connection() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def execute_command(self, command: str, *args) -> str:
        """Execute an INSERT/UPDATE/DELETE command"""
        async with self.get_connection() as conn:
            result = await conn.execute(command, *args)
            return result

    async def fetch_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Fetch single row"""
        async with self.get_connection() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_val(self, query: str, *args) -> Any:
        """Fetch single value"""
        async with self.get_connection() as conn:
            return await conn.fetchval(query, *args)

    # Book-related methods
    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get all categories"""
        query = "SELECT id, name, created_at FROM category ORDER BY name"
        return await self.execute_query(query)

    async def get_books_by_category(self, category_id: int) -> List[Dict[str, Any]]:
        """Get books by category"""
        query = """
            SELECT b.id, b.title, b.author, b.publication_year, b.file_name, c.name as category_name
            FROM books b
            JOIN category c ON b.category_id = c.id
            WHERE b.category_id = $1
            ORDER BY b.title
        """
        return await self.execute_query(query, category_id)

    async def get_book_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Get book by title"""
        query = """
            SELECT b.*, c.name as category_name
            FROM books b
            JOIN category c ON b.category_id = c.id
            WHERE b.title = $1
        """
        return await self.fetch_one(query, title)

    async def check_book_exists(self, file_hash: str) -> bool:
        """Check if book exists by file hash"""
        query = "SELECT COUNT(*) FROM books WHERE file_hash = $1"
        count = await self.fetch_val(query, file_hash)
        return count > 0

    async def insert_book(self, book_data: Dict[str, Any]) -> int:
        """Insert new book and return ID"""
        query = """
            INSERT INTO books (category_id, title, author, publication_year, file_hash, file_name)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
        """
        return await self.fetch_val(
            query,
            book_data['category_id'],
            book_data['title'],
            book_data.get('author'),
            book_data.get('publication_year'),
            book_data['file_hash'],
            book_data['file_name']
        )

    # Chat session methods
    async def create_chat_session(self, user_id: str, book_id: int, session_name: str = None) -> str:
        """Create new chat session"""
        query = """
            INSERT INTO chat_sessions (user_id, book_id, session_name)
            VALUES ($1, $2, $3)
            RETURNING id
        """
        return await self.fetch_val(query, user_id, book_id, session_name)

    async def get_chat_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get chat session by ID"""
        query = """
            SELECT cs.*, b.title as book_title, c.name as category_name
            FROM chat_sessions cs
            JOIN books b ON cs.book_id = b.id
            JOIN category c ON b.category_id = c.id
            WHERE cs.id = $1
        """
        return await self.fetch_one(query, session_id)

    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all sessions for a user"""
        query = """
            SELECT cs.*, b.title as book_title, c.name as category_name
            FROM chat_sessions cs
            JOIN books b ON cs.book_id = b.id
            JOIN category c ON b.category_id = c.id
            WHERE cs.user_id = $1
            ORDER BY cs.updated_at DESC
        """
        return await self.execute_query(query, user_id)

    async def add_chat_message(self, session_id: str, message_type: str, content: str, metadata: Dict = None) -> int:
        """Add message to chat session"""
        query = """
            INSERT INTO chat_messages (session_id, message_type, content, metadata)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """
        return await self.fetch_val(query, session_id, message_type, content, metadata)

    async def get_chat_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chat history for session"""
        query = """
            SELECT message_type, content, metadata, created_at
            FROM chat_messages
            WHERE session_id = $1
            ORDER BY created_at ASC
            LIMIT $2
        """
        return await self.execute_query(query, session_id, limit)

    async def update_session_timestamp(self, session_id: str):
        """Update session's last activity timestamp"""
        query = "UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = $1"
        await self.execute_command(query, session_id)

# Global database instance
db_manager: Optional[DatabaseManager] = None

def get_database() -> DatabaseManager:
    """Get database manager instance"""
    global db_manager
    if not db_manager:
        database_url = os.getenv("DATABASE_URL", "postgresql://zakerly_user:zakerly_password@localhost:5432/zakerly_db")
        db_manager = DatabaseManager(database_url)
    return db_manager