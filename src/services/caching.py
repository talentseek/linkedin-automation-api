"""
Caching service for API responses using Redis.

This module provides:
- Response caching for frequently accessed data
- Cache invalidation strategies
- Cache key management
- Performance monitoring
"""

import json
import hashlib
import logging
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
from functools import wraps
import redis
from flask import request, jsonify, current_app

logger = logging.getLogger(__name__)

class CacheService:
    """Redis-based caching service for API responses."""
    
    def __init__(self, redis_url: str = None):
        """Initialize the cache service."""
        self.redis_url = redis_url or current_app.config.get('REDIS_URL', 'redis://localhost:6379/0')
        self.redis_client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.redis_client = None
    
    def _generate_cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a unique cache key."""
        # Create a hash of the arguments
        key_data = f"{prefix}:{':'.join(str(arg) for arg in args)}"
        if kwargs:
            # Sort kwargs for consistent key generation
            sorted_kwargs = sorted(kwargs.items())
            key_data += f":{':'.join(f'{k}={v}' for k, v in sorted_kwargs)}"
        
        # Create a hash of the request data for more specific caching
        request_data = {
            'method': request.method,
            'args': dict(request.args),
            'json': request.get_json() if request.is_json else None
        }
        request_hash = hashlib.md5(json.dumps(request_data, sort_keys=True).encode()).hexdigest()
        
        return f"api:{key_data}:{request_hash}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        if not self.redis_client:
            return None
        
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {str(e)}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set a value in cache with TTL."""
        if not self.redis_client:
            return False
        
        try:
            serialized_value = json.dumps(value)
            return self.redis_client.setex(key, ttl, serialized_value)
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        if not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {str(e)}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        if not self.redis_client:
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Error deleting cache pattern {pattern}: {str(e)}")
            return 0
    
    def invalidate_client_cache(self, client_id: str):
        """Invalidate all cache entries for a specific client."""
        pattern = f"api:client:{client_id}:*"
        deleted_count = self.delete_pattern(pattern)
        logger.info(f"Invalidated {deleted_count} cache entries for client {client_id}")
    
    def invalidate_campaign_cache(self, campaign_id: str):
        """Invalidate all cache entries for a specific campaign."""
        pattern = f"api:campaign:{campaign_id}:*"
        deleted_count = self.delete_pattern(pattern)
        logger.info(f"Invalidated {deleted_count} cache entries for campaign {campaign_id}")
    
    def invalidate_lead_cache(self, lead_id: str):
        """Invalidate all cache entries for a specific lead."""
        pattern = f"api:lead:{lead_id}:*"
        deleted_count = self.delete_pattern(pattern)
        logger.info(f"Invalidated {deleted_count} cache entries for lead {lead_id}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.redis_client:
            return {"error": "Redis not connected"}
        
        try:
            info = self.redis_client.info()
            return {
                "connected": True,
                "total_keys": info.get('db0', {}).get('keys', 0),
                "memory_usage": info.get('used_memory_human', 'N/A'),
                "uptime": info.get('uptime_in_seconds', 0),
                "connected_clients": info.get('connected_clients', 0)
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {"error": str(e)}

# Global cache service instance
cache_service = None

def get_cache_service() -> CacheService:
    """Get the global cache service instance."""
    global cache_service
    if cache_service is None:
        cache_service = CacheService()
    return cache_service

def cache_response(prefix: str, ttl: int = 300, key_args: List[str] = None):
    """
    Decorator to cache API responses.
    
    Args:
        prefix: Cache key prefix
        ttl: Time to live in seconds
        key_args: List of argument names to include in cache key
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache_service()
            
            # Generate cache key
            if key_args:
                # Use specific arguments for cache key
                key_values = []
                for arg_name in key_args:
                    if arg_name in kwargs:
                        key_values.append(kwargs[arg_name])
                    else:
                        # Try to get from args based on position
                        key_values.append(args[len(key_values)] if len(key_values) < len(args) else None)
                cache_key = cache._generate_cache_key(prefix, *key_values)
            else:
                # Use all arguments
                cache_key = cache._generate_cache_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.info(f"Cache hit for key: {cache_key}")
                return jsonify(cached_response)
            
            # Execute function and cache result
            logger.info(f"Cache miss for key: {cache_key}")
            response = func(*args, **kwargs)
            
            # Cache successful responses only
            if hasattr(response, 'status_code') and response.status_code == 200:
                try:
                    response_data = response.get_json()
                    cache.set(cache_key, response_data, ttl)
                except Exception as e:
                    logger.error(f"Error caching response: {str(e)}")
            
            return response
        return wrapper
    return decorator

def invalidate_cache_on_change(resource_type: str, resource_id_arg: str):
    """
    Decorator to invalidate cache when data changes.
    
    Args:
        resource_type: Type of resource (client, campaign, lead, etc.)
        resource_id_arg: Name of the argument containing the resource ID
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Execute the function first
            response = func(*args, **kwargs)
            
            # Invalidate cache if operation was successful
            if hasattr(response, 'status_code') and response.status_code in [200, 201]:
                cache = get_cache_service()
                resource_id = kwargs.get(resource_id_arg)
                
                if resource_id:
                    if resource_type == 'client':
                        cache.invalidate_client_cache(resource_id)
                    elif resource_type == 'campaign':
                        cache.invalidate_campaign_cache(resource_id)
                    elif resource_type == 'lead':
                        cache.invalidate_lead_cache(resource_id)
                    
                    logger.info(f"Invalidated cache for {resource_type} {resource_id}")
            
            return response
        return wrapper
    return decorator

# Cache configuration
CACHE_CONFIG = {
    'clients': {
        'list': 300,  # 5 minutes
        'detail': 600,  # 10 minutes
    },
    'campaigns': {
        'list': 300,  # 5 minutes
        'detail': 600,  # 10 minutes
        'leads': 180,  # 3 minutes
    },
    'leads': {
        'list': 180,  # 3 minutes
        'detail': 300,  # 5 minutes
    },
    'analytics': {
        'campaign': 900,  # 15 minutes
        'comparative': 1800,  # 30 minutes
        'real_time': 60,  # 1 minute
    }
}
