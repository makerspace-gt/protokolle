"""Vikunja API client for fetching task data."""

import logging
from typing import Dict, List, Any, Optional
import requests
from requests.exceptions import RequestException, HTTPError, Timeout

from .config import Config

logger = logging.getLogger(__name__)

HTTP_OK = 200
REQUEST_TIMEOUT = 30


class VikunjaAPIError(Exception):
    """Custom exception for Vikunja API errors."""
    pass


class VikunjaClient:
    """Client for interacting with the Vikunja API."""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {config.vikunja_api_token}',
            'Content-Type': 'application/json'
        })
    
    def _make_request(self, endpoint: str, method: str = 'GET') -> Dict[str, Any]:
        """Make a request to the Vikunja API with proper error handling."""
        url = f"{self.config.vikunja_base_url}/api/v1/{endpoint.lstrip('/')}"
        
        try:
            logger.debug(f"Making {method} request to {url}")
            response = self.session.request(method, url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            if response.status_code != HTTP_OK:
                raise VikunjaAPIError(f"Unexpected status code: {response.status_code}")
            
            return response.json()
            
        except Timeout as e:
            logger.error(f"Request timeout for {url}")
            raise VikunjaAPIError(f"Request timeout: {e}")
        except HTTPError as e:
            logger.error(f"HTTP error for {url}: {e}")
            raise VikunjaAPIError(f"HTTP error: {e}")
        except RequestException as e:
            logger.error(f"Request error for {url}: {e}")
            raise VikunjaAPIError(f"Request error: {e}")
        except ValueError as e:
            logger.error(f"JSON decode error for {url}: {e}")
            raise VikunjaAPIError(f"Invalid JSON response: {e}")
    
    def get_labels(self) -> List[Dict[str, Any]]:
        """Fetch all labels from Vikunja."""
        logger.info("Fetching labels")
        return self._make_request("labels")
    
    def get_projects(self) -> List[Dict[str, Any]]:
        """Fetch all projects from Vikunja."""
        logger.info("Fetching projects")
        return self._make_request("projects")
    
    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Fetch a specific task by ID."""
        logger.info(f"Fetching task {task_id}")
        return self._make_request(f"tasks/{task_id}")
    
    def get_task_comments(self, task_id: str) -> List[Dict[str, Any]]:
        """Fetch comments for a specific task."""
        logger.info(f"Fetching comments for task {task_id}")
        try:
            return self._make_request(f"tasks/{task_id}/comments")
        except VikunjaAPIError as e:
            logger.warning(f"Failed to fetch comments for task {task_id}: {e}")
            return []
    
    def get_meta_task_with_comments(self) -> Dict[str, Any]:
        """Fetch meta task and all comments for related tasks."""
        logger.info(f"Fetching meta task {self.config.meta_task_id}")
        meta_task = self.get_task(self.config.meta_task_id)
        
        # Fetch comments for each related task
        if meta_task.get("related_tasks") and meta_task["related_tasks"].get("related"):
            for task in meta_task["related_tasks"]["related"]:
                task_id = task["id"]
                logger.debug(f"Fetching comments for related task {task_id}")
                task["comments"] = self.get_task_comments(str(task_id))
        
        return meta_task
    
    def close(self):
        """Close the session."""
        self.session.close()
