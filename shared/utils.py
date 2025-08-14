import hashlib
import re
import logging
from typing import Optional, Dict, Any
import redis
import json
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

def calculate_file_hash(content: bytes) -> str:
    """Calculate SHA256 hash of file content"""
    return hashlib.sha256(content).hexdigest()

def sanitize_title_for_table(title: str) -> str:
    """Sanitize title for use as database table name"""
    # Convert to uppercase
    sanitized = title.upper()
    # Replace spaces with underscores
    sanitized = re.sub(r'\s+', '_', sanitized)
    # Remove any characters that are not uppercase letters, numbers, or underscores
    sanitized = re.sub(r'[^A-Z0-9_]', '', sanitized)
    return sanitized

def extract_category_id(subject: str) -> int:
    """Map subject to category ID"""
    category_mapping = {
        "math": 1,
        "science": 2,
        "physics": 3,
        "chemistry": 4,
        "history": 5,
        "geology": 6,
        "general": 7
    }
    return category_mapping.get(subject.lower(), 7)  # Default to 'general'

class RedisManager:
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client: Optional[redis.Redis] = None

    def connect(self):
        """Connect to Redis"""
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            self.client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from Redis")

    def set_cache(self, key: str, value: Any, expire_seconds: int = 3600):
        """Set cache value with expiration"""
        if not self.client:
            return False
        try:
            serialized_value = json.dumps(value, default=str)
            return self.client.setex(key, expire_seconds, serialized_value)
        except Exception as e:
            logger.error(f"Failed to set cache: {e}")
            return False

    def get_cache(self, key: str) -> Optional[Any]:
        """Get cache value"""
        if not self.client:
            return None
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Failed to get cache: {e}")
            return None

    def delete_cache(self, key: str) -> bool:
        """Delete cache key"""
        if not self.client:
            return False
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Failed to delete cache: {e}")
            return False

    def set_session(self, session_id: str, data: Dict[str, Any], expire_hours: int = 24):
        """Set session data"""
        expire_seconds = expire_hours * 3600
        return self.set_cache(f"session:{session_id}", data, expire_seconds)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        return self.get_cache(f"session:{session_id}")

    def extend_session(self, session_id: str, expire_hours: int = 24):
        """Extend session expiration"""
        if not self.client:
            return False
        try:
            expire_seconds = expire_hours * 3600
            return self.client.expire(f"session:{session_id}", expire_seconds)
        except Exception as e:
            logger.error(f"Failed to extend session: {e}")
            return False

# Global Redis instance
redis_manager: Optional[RedisManager] = None

def get_redis() -> RedisManager:
    """Get Redis manager instance"""
    global redis_manager
    if not redis_manager:
        redis_manager = RedisManager()
        redis_manager.connect()
    return redis_manager

def setup_logging(service_name: str, level: str = "INFO"):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=f'%(asctime)s - {service_name} - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(f'/app/logs/{service_name}.log', mode='a')
        ]
    )

def validate_file_type(mime_type: str) -> bool:
    """Validate if file type is supported"""
    supported_types = [
        'application/pdf',
        'text/plain',
        'text/markdown',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ]
    return mime_type in supported_types

def generate_session_id() -> str:
    """Generate unique session ID"""
    import uuid
    return str(uuid.uuid4())

def format_timestamp(dt: datetime) -> str:
    """Format datetime for API responses"""
    return dt.isoformat()

def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse timestamp string to datetime"""
    return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

class MetricsCollector:
    """Simple metrics collector for monitoring"""
    
    def __init__(self):
        self.metrics = {}
        self.redis = get_redis()

    def increment_counter(self, metric_name: str, labels: Dict[str, str] = None):
        """Increment a counter metric"""
        key = f"metrics:counter:{metric_name}"
        if labels:
            key += ":" + ":".join(f"{k}={v}" for k, v in labels.items())
        
        try:
            if self.redis.client:
                self.redis.client.incr(key)
        except Exception as e:
            logger.error(f"Failed to increment metric {metric_name}: {e}")

    def record_histogram(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Record a histogram value"""
        key = f"metrics:histogram:{metric_name}"
        if labels:
            key += ":" + ":".join(f"{k}={v}" for k, v in labels.items())
        
        try:
            if self.redis.client:
                # Simple histogram implementation using Redis lists
                self.redis.client.lpush(f"{key}:values", value)
                self.redis.client.ltrim(f"{key}:values", 0, 999)  # Keep last 1000 values
        except Exception as e:
            logger.error(f"Failed to record histogram {metric_name}: {e}")

# Global metrics collector
metrics = MetricsCollector()