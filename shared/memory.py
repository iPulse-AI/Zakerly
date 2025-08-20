import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

from langchain.memory.chat_memory import BaseChatMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field

from database import DatabaseManager

logger = logging.getLogger(__name__)

class MemoryType(str, Enum):
    ENTITY = "entity"
    SUMMARY = "summary"
    CONTEXT = "context"

class PostgreSQLAgentMemory:
    """
    PostgreSQL-based memory system for LangChain agents using existing chat tables.
    
    Features:
    - Uses existing chat_messages table for conversation history
    - Adds session_memory table for entities, summaries, and context
    - Entity extraction and tracking
    - Conversation summarization
    - Context persistence
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        session_id: str,
        max_conversation_length: int = 20,
        summary_threshold: int = 50,
        entity_extraction_enabled: bool = True,
        memory_ttl_hours: int = 24 * 7,  # 7 days
        **kwargs
    ):
        # Set attributes directly
        self.db_manager = db_manager
        self.session_id = session_id
        self.max_conversation_length = max_conversation_length
        self.summary_threshold = summary_threshold
        self.entity_extraction_enabled = entity_extraction_enabled
        self.memory_ttl_hours = memory_ttl_hours
        
        # Initialize memory tables if not exists
        asyncio.create_task(self._initialize_memory_tables())
    
    async def _initialize_memory_tables(self):
        """Initialize session_memory table for enhanced memory features"""
        try:
            async with self.db_manager.get_connection() as conn:
                # Create session_memory table for entities, summaries, and context
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS session_memory (
                        id SERIAL PRIMARY KEY,
                        session_id UUID NOT NULL,
                        memory_type VARCHAR(50) NOT NULL,
                        key VARCHAR(255) NOT NULL,
                        value JSONB NOT NULL,
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        UNIQUE(session_id, memory_type, key),
                        CONSTRAINT fk_session_memory
                            FOREIGN KEY (session_id)
                            REFERENCES chat_sessions(id) ON DELETE CASCADE
                    )
                """)
                
                # Create indexes
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_memory_session_type 
                    ON session_memory(session_id, memory_type)
                """)
                
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_memory_expires 
                    ON session_memory(expires_at) WHERE expires_at IS NOT NULL
                """)
                
                logger.info("Session memory tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing memory tables: {e}")
    
    @property
    def memory_variables(self) -> List[str]:
        """Return memory variables"""
        return ["history", "entities", "summary", "context"]
    
    def clear(self) -> None:
        """Clear all enhanced memory for this session (keeps chat_messages)"""
        asyncio.create_task(self._clear_memory())
    
    async def _clear_memory(self):
        """Clear enhanced memory for this session"""
        try:
            async with self.db_manager.get_connection() as conn:
                await conn.execute(
                    "DELETE FROM session_memory WHERE session_id = $1",
                    self.session_id
                )
            logger.info(f"Cleared enhanced memory for session {self.session_id}")
        except Exception as e:
            logger.error(f"Error clearing memory: {e}")
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Load memory variables synchronously (required by LangChain)"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._load_memory_variables_async(inputs))
                    return future.result()
            else:
                return loop.run_until_complete(self._load_memory_variables_async(inputs))
        except RuntimeError:
            return asyncio.run(self._load_memory_variables_async(inputs))
    
    async def _load_memory_variables_async(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Load memory variables asynchronously"""
        try:
            # Clean up expired memories first
            await self._cleanup_expired_memories()
            
            memory_vars = {}
            
            # Load conversation history from chat_messages
            history = await self._load_conversation_memory()
            memory_vars["history"] = history
            
            # Load entities from session_memory
            entities = await self._load_entity_memory()
            memory_vars["entities"] = entities
            
            # Load summary from session_memory
            summary = await self._load_summary_memory()
            memory_vars["summary"] = summary
            
            # Load context from session_memory
            context = await self._load_context_memory()
            memory_vars["context"] = context
            
            return memory_vars
            
        except Exception as e:
            logger.error(f"Error loading memory variables: {e}")
            return {"history": [], "entities": {}, "summary": "", "context": {}}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save context synchronously (required by LangChain)"""
        asyncio.create_task(self._save_context_async(inputs, outputs))
    
    async def _save_context_async(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save context asynchronously"""
        try:
            # Extract messages from inputs and outputs
            human_message = inputs.get("input", "")
            ai_message = outputs.get("output", "")
            
            # Extract and save entities if enabled
            if self.entity_extraction_enabled and (human_message or ai_message):
                await self._extract_and_save_entities(human_message, ai_message)
            
            # Check if we need to create a summary
            await self._check_and_create_summary()
            
        except Exception as e:
            logger.error(f"Error saving context: {e}")
    
    async def _load_conversation_memory(self) -> List[BaseMessage]:
        """Load conversation history from existing chat_messages table"""
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT message_type, content, created_at
                    FROM chat_messages
                    WHERE session_id = $1
                    ORDER BY created_at ASC
                    LIMIT $2
                """, self.session_id, self.max_conversation_length)
                
                messages = []
                for row in rows:
                    if row['message_type'] == 'user':
                        messages.append(HumanMessage(content=row['content']))
                    elif row['message_type'] == 'assistant':
                        messages.append(AIMessage(content=row['content']))
                
                return messages
                
        except Exception as e:
            logger.error(f"Error loading conversation memory: {e}")
            return []
    
    async def _load_entity_memory(self) -> Dict[str, Any]:
        """Load entity memory from session_memory table"""
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT key, value
                    FROM session_memory
                    WHERE session_id = $1 AND memory_type = $2
                """, self.session_id, MemoryType.ENTITY.value)
                
                entities = {}
                for row in rows:
                    entities[row['key']] = row['value']
                
                return entities
                
        except Exception as e:
            logger.error(f"Error loading entity memory: {e}")
            return {}
    
    async def _extract_and_save_entities(self, human_message: str, ai_message: str):
        """Extract and save entities from messages"""
        try:
            # Simple entity extraction
            entities = self._simple_entity_extraction(human_message + " " + ai_message)
            
            for entity, info in entities.items():
                await self._save_entity(entity, info)
                
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
    
    def _simple_entity_extraction(self, text: str) -> Dict[str, Dict[str, Any]]:
        """Simple entity extraction"""
        entities = {}
        
        # Extract potential entities (capitalized words)
        words = text.split()
        for i, word in enumerate(words):
            # Look for capitalized words (potential proper nouns)
            if word.istitle() and len(word) > 2 and word.isalpha():
                context = " ".join(words[max(0, i-2):i+3])
                entities[word] = {
                    "type": "ENTITY",
                    "context": context,
                    "frequency": entities.get(word, {}).get("frequency", 0) + 1,
                    "last_mentioned": datetime.now().isoformat()
                }
        
        return entities
    
    async def _save_entity(self, entity: str, info: Dict[str, Any]):
        """Save or update an entity"""
        try:
            expires_at = datetime.now() + timedelta(hours=self.memory_ttl_hours)
            
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO session_memory (session_id, memory_type, key, value, expires_at)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (session_id, memory_type, key)
                    DO UPDATE SET 
                        value = EXCLUDED.value,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = CURRENT_TIMESTAMP
                """,
                self.session_id,
                MemoryType.ENTITY.value,
                entity,
                json.dumps(info),
                expires_at
                )
                
        except Exception as e:
            logger.error(f"Error saving entity: {e}")
    
    async def _load_summary_memory(self) -> str:
        """Load conversation summary"""
        try:
            async with self.db_manager.get_connection() as conn:
                row = await conn.fetchrow("""
                    SELECT value
                    FROM session_memory
                    WHERE session_id = $1 AND memory_type = $2 AND key = 'conversation_summary'
                """, self.session_id, MemoryType.SUMMARY.value)
                
                if row:
                    return row['value'].get('summary', '')
                return ''
                
        except Exception as e:
            logger.error(f"Error loading summary memory: {e}")
            return ''
    
    async def _check_and_create_summary(self):
        """Check if we need to create a conversation summary"""
        try:
            async with self.db_manager.get_connection() as conn:
                # Count chat messages
                count = await conn.fetchval("""
                    SELECT COUNT(*)
                    FROM chat_messages
                    WHERE session_id = $1
                """, self.session_id)
                
                if count >= self.summary_threshold:
                    await self._create_conversation_summary()
                    
        except Exception as e:
            logger.error(f"Error checking summary creation: {e}")
    
    async def _create_conversation_summary(self):
        """Create a conversation summary"""
        try:
            async with self.db_manager.get_connection() as conn:
                # Get older messages to summarize
                rows = await conn.fetch("""
                    SELECT message_type, content, created_at
                    FROM chat_messages
                    WHERE session_id = $1
                    ORDER BY created_at ASC
                    LIMIT $2
                """, self.session_id, self.summary_threshold // 2)
                
                # Create a simple summary
                messages = []
                for row in rows:
                    messages.append(f"{row['message_type']}: {row['content'][:100]}...")
                
                summary = f"Summary of {len(messages)} messages from conversation. " + \
                         "Key topics discussed: " + ", ".join(messages[:3])
                
                # Save summary
                expires_at = datetime.now() + timedelta(hours=self.memory_ttl_hours)
                await conn.execute("""
                    INSERT INTO session_memory (session_id, memory_type, key, value, expires_at)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (session_id, memory_type, key)
                    DO UPDATE SET 
                        value = EXCLUDED.value,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = CURRENT_TIMESTAMP
                """,
                self.session_id,
                MemoryType.SUMMARY.value,
                'conversation_summary',
                json.dumps({"summary": summary, "message_count": len(messages)}),
                expires_at
                )
                
                logger.info(f"Created conversation summary for session {self.session_id}")
                
        except Exception as e:
            logger.error(f"Error creating conversation summary: {e}")
    
    async def _load_context_memory(self) -> Dict[str, Any]:
        """Load context memory"""
        try:
            async with self.db_manager.get_connection() as conn:
                rows = await conn.fetch("""
                    SELECT key, value
                    FROM session_memory
                    WHERE session_id = $1 AND memory_type = $2
                """, self.session_id, MemoryType.CONTEXT.value)
                
                context = {}
                for row in rows:
                    context[row['key']] = row['value']
                
                return context
                
        except Exception as e:
            logger.error(f"Error loading context memory: {e}")
            return {}
    
    async def save_context_data(self, key: str, value: Any, metadata: Dict[str, Any] = None):
        """Save context data"""
        try:
            expires_at = datetime.now() + timedelta(hours=self.memory_ttl_hours)
            
            async with self.db_manager.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO session_memory (session_id, memory_type, key, value, metadata, expires_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (session_id, memory_type, key)
                    DO UPDATE SET 
                        value = EXCLUDED.value,
                        metadata = EXCLUDED.metadata,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = CURRENT_TIMESTAMP
                """,
                self.session_id,
                MemoryType.CONTEXT.value,
                key,
                json.dumps(value) if not isinstance(value, str) else value,
                json.dumps(metadata or {}),
                expires_at
                )
                
        except Exception as e:
            logger.error(f"Error saving context data: {e}")
    
    async def _cleanup_expired_memories(self):
        """Clean up expired memories"""
        try:
            async with self.db_manager.get_connection() as conn:
                result = await conn.execute("""
                    DELETE FROM session_memory
                    WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
                """)
                
                if "DELETE" in result:
                    count = int(result.split()[-1])
                    if count > 0:
                        logger.info(f"Cleaned up {count} expired memory entries")
                        
        except Exception as e:
            logger.error(f"Error cleaning up expired memories: {e}")
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics for this session"""
        try:
            async with self.db_manager.get_connection() as conn:
                # Get chat message count
                chat_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM chat_messages WHERE session_id = $1
                """, self.session_id)
                
                # Get memory stats
                memory_stats = await conn.fetch("""
                    SELECT 
                        memory_type,
                        COUNT(*) as count,
                        MIN(created_at) as oldest,
                        MAX(updated_at) as newest
                    FROM session_memory
                    WHERE session_id = $1
                    GROUP BY memory_type
                """, self.session_id)
                
                stats = {
                    "session_id": self.session_id,
                    "chat_messages": chat_count,
                    "memory_types": {}
                }
                
                for row in memory_stats:
                    stats["memory_types"][row['memory_type']] = {
                        "count": row['count'],
                        "oldest": row['oldest'],
                        "newest": row['newest']
                    }
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {}

class MemoryManager:
    """Manager for handling multiple memory instances"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._memory_instances: Dict[str, PostgreSQLAgentMemory] = {}
    
    def get_memory(self, session_id: str, **kwargs) -> PostgreSQLAgentMemory:
        """Get or create memory instance for session"""
        if session_id not in self._memory_instances:
            self._memory_instances[session_id] = PostgreSQLAgentMemory(
                db_manager=self.db_manager,
                session_id=session_id,
                **kwargs
            )
        return self._memory_instances[session_id]
    
    def clear_memory(self, session_id: str):
        """Clear memory for session"""
        if session_id in self._memory_instances:
            self._memory_instances[session_id].clear()
            del self._memory_instances[session_id]
    
    async def cleanup_all_expired(self):
        """Clean up all expired memories across all sessions"""
        try:
            async with self.db_manager.get_connection() as conn:
                result = await conn.execute("""
                    DELETE FROM session_memory
                    WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
                """)
                
                if "DELETE" in result:
                    count = int(result.split()[-1])
                    logger.info(f"Cleaned up {count} expired memory entries across all sessions")
                    
        except Exception as e:
            logger.error(f"Error cleaning up all expired memories: {e}")