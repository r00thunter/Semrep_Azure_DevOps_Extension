#!/usr/bin/env python3
"""
Shared API utilities for Semgrep Azure DevOps Extension

Provides:
- Retry logic with exponential backoff
- Rate limit handling
- Deployment slug caching
- Batch API call support
"""

from __future__ import annotations

import json
import logging
import os
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

import requests


logger = logging.getLogger("api_utils")


class RateLimitError(Exception):
    """Raised when rate limit is hit"""
    pass


class APIError(Exception):
    """Generic API error"""
    pass


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_status_codes: tuple = (429, 500, 502, 503, 504),
    retryable_exceptions: tuple = (requests.RequestException,)
):
    """
    Decorator for retrying API calls with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        retryable_status_codes: HTTP status codes that should trigger retry
        retryable_exceptions: Exceptions that should trigger retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    response = func(*args, **kwargs)
                    
                    # Check if response is a requests.Response object
                    if hasattr(response, 'status_code'):
                        status_code = response.status_code
                        
                        # Handle rate limiting
                        if status_code == 429:
                            retry_after = response.headers.get('Retry-After')
                            if retry_after:
                                delay = float(retry_after)
                            else:
                                delay = min(delay * exponential_base, max_delay)
                            
                            if attempt < max_retries:
                                logger.warning(f"Rate limited (429). Retrying after {delay:.1f}s (attempt {attempt + 1}/{max_retries + 1})")
                                time.sleep(delay)
                                delay = min(delay * exponential_base, max_delay)
                                continue
                            else:
                                raise RateLimitError(f"Rate limit exceeded after {max_retries + 1} attempts")
                        
                        # Handle other retryable status codes
                        if status_code in retryable_status_codes and attempt < max_retries:
                            logger.warning(f"API returned {status_code}. Retrying after {delay:.1f}s (attempt {attempt + 1}/{max_retries + 1})")
                            time.sleep(delay)
                            delay = min(delay * exponential_base, max_delay)
                            continue
                    
                    return response
                    
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"Request failed: {e}. Retrying after {delay:.1f}s (attempt {attempt + 1}/{max_retries + 1})")
                        time.sleep(delay)
                        delay = min(delay * exponential_base, max_delay)
                    else:
                        logger.error(f"Request failed after {max_retries + 1} attempts: {e}")
                        raise
            
            if last_exception:
                raise last_exception
            
            return None
            
        return wrapper
    return decorator


class DeploymentSlugCache:
    """Cache for deployment slug to avoid repeated API calls"""
    
    _cache: Optional[str] = None
    _cache_file: str = ".semgrep_deployment_slug_cache"
    
    @classmethod
    def get(cls, session: requests.Session, token: str, force_refresh: bool = False) -> str:
        """Get deployment slug from cache or API"""
        if not force_refresh and cls._cache:
            logger.debug("Using cached deployment slug")
            return cls._cache
        
        # Try to load from file cache
        if not force_refresh and os.path.exists(cls._cache_file):
            try:
                with open(cls._cache_file, 'r') as f:
                    cached_data = json.load(f)
                    # Cache valid for 1 hour
                    if time.time() - cached_data.get('timestamp', 0) < 3600:
                        cls._cache = cached_data.get('slug')
                        logger.debug("Loaded deployment slug from file cache")
                        return cls._cache
            except Exception as e:
                logger.debug(f"Failed to load cache: {e}")
        
        # Fetch from API
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        url = "https://semgrep.dev/api/v1/deployments"
        
        @retry_with_backoff(max_retries=3)
        def fetch_slug():
            resp = session.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp
        
        try:
            resp = fetch_slug()
            data = resp.json()
            deployments = data.get("deployments", [])
            if not deployments:
                raise RuntimeError("No deployments found in Semgrep account")
            
            slug = deployments[0].get("slug")
            if not slug:
                raise RuntimeError("Deployment slug not found in API response")
            
            # Cache it
            cls._cache = slug
            try:
                with open(cls._cache_file, 'w') as f:
                    json.dump({'slug': slug, 'timestamp': time.time()}, f)
            except Exception as e:
                logger.debug(f"Failed to save cache: {e}")
            
            logger.info(f"Fetched and cached deployment slug: {slug}")
            return slug
            
        except requests.RequestException as e:
            logger.error(f"Failed to get deployment slug: {e}")
            raise
    
    @classmethod
    def clear(cls):
        """Clear the cache"""
        cls._cache = None
        if os.path.exists(cls._cache_file):
            try:
                os.remove(cls._cache_file)
            except Exception:
                pass


def batch_api_calls(
    items: list,
    batch_size: int,
    api_call: Callable,
    *args,
    **kwargs
) -> list:
    """
    Process items in batches to avoid overwhelming the API
    
    Args:
        items: List of items to process
        batch_size: Number of items per batch
        api_call: Function to call for each batch
        *args, **kwargs: Additional arguments for api_call
    
    Returns:
        List of results from all batches
    """
    results = []
    total_batches = (len(items) + batch_size - 1) // batch_size
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        
        logger.debug(f"Processing batch {batch_num}/{total_batches} ({len(batch)} items)")
        
        try:
            batch_results = api_call(batch, *args, **kwargs)
            if isinstance(batch_results, list):
                results.extend(batch_results)
            else:
                results.append(batch_results)
        except Exception as e:
            logger.error(f"Batch {batch_num} failed: {e}")
            # Continue with next batch (partial failure handling)
            continue
        
        # Small delay between batches to avoid rate limits
        if i + batch_size < len(items):
            time.sleep(0.5)
    
    return results


def handle_partial_failures(
    items: list,
    process_func: Callable,
    *args,
    **kwargs
) -> Tuple[list, list]:
    """
    Process items with partial failure handling
    
    Returns:
        Tuple of (successful_results, failed_items)
    """
    successful = []
    failed = []
    
    for item in items:
        try:
            result = process_func(item, *args, **kwargs)
            successful.append(result)
        except Exception as e:
            logger.warning(f"Failed to process item {item}: {e}")
            failed.append({'item': item, 'error': str(e)})
    
    if failed:
        logger.warning(f"Processed {len(successful)}/{len(items)} items successfully. {len(failed)} failed.")
    
    return successful, failed
