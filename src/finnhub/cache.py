"""
Cache for storing and retrieving stock data.
"""

import json
import logging
from typing import Optional, Dict
import redis
from datetime import timedelta

logger = logging.getLogger(__name__)

class StockCache:
    """Redis-based cache for stock data."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0", ttl_minutes: int = 5):
        """Initialize cache.
        
        Args:
            redis_url: Redis connection URL
            ttl_minutes: Time to live for cached data in minutes
        """
        self.redis_client = redis.from_url(redis_url)
        self.ttl = timedelta(minutes=ttl_minutes)
    
    def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get cached quote.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Cached quote or None if not found
        """
        try:
            key = f"quote:{symbol}"
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error retrieving quote from cache: {e}")
            return None
    
    def set_quote(self, symbol: str, quote: Dict) -> bool:
        """Cache a quote.
        
        Args:
            symbol: Stock symbol
            quote: Quote data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = f"quote:{symbol}"
            self.redis_client.setex(
                key,
                self.ttl,
                json.dumps(quote)
            )
            return True
        except Exception as e:
            logger.error(f"Error caching quote: {e}")
            return False
    
    def clear_cache(self) -> bool:
        """Clear all cached data.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.redis_client.flushdb()
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
