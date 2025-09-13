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
    
    def _make_request(self, endpoint: str, method: str = 'GET', data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a request to the Vikunja API with proper error handling."""
        url = f"{self.config.vikunja_base_url}/api/v1/{endpoint.lstrip('/')}"
        
        try:
            logger.debug(f"Making {method} request to {url}")
            response = self.session.request(method, url, json=data, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            if response.status_code not in [HTTP_OK, 201]:  # Accept 200 and 201
                raise VikunjaAPIError(f"Unexpected status code: {response.status_code}")
            
            return response.json()
            
        except Timeout as e:
            logger.error(f"Request timeout for {url}")
            raise VikunjaAPIError(f"Request timeout: {e}")
        except HTTPError as e:
            logger.error(f"HTTP error for {url}: {e}")
            try:
                error_detail = response.text
                logger.error(f"Response body: {error_detail}")
            except:
                pass
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
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Fetch all tasks from Vikunja."""
        logger.info("Fetching all tasks")
        return self._make_request("tasks/all")
    
    def get_tasks_by_label(self, label_id: int) -> List[Dict[str, Any]]:
        """Fetch all tasks with a specific label."""
        logger.info(f"Fetching tasks with label ID {label_id}")
        return self._make_request(f"tasks/all?filter=labels={label_id}")
    
    def find_task_by_title(self, title: str, project_id: int = None) -> Dict[str, Any]:
        """Find a task by title, optionally within a specific project."""
        logger.info(f"Searching for task with title: {title}")
        
        # Get all tasks and filter by title
        all_tasks = self.get_all_tasks()
        logger.debug(f"Retrieved {len(all_tasks)} tasks")
        
        for task in all_tasks:
            task_title = task.get('title')
            task_project_id = task.get('project_id')
            
            if task_title == title:
                logger.debug(f"Found matching title: {task_title} (project: {task_project_id})")
                if project_id is None or task_project_id == project_id:
                    logger.info(f"Found task: {task_title} (ID: {task.get('id')}, project: {task_project_id})")
                    return task
                else:
                    logger.debug(f"Title matches but wrong project: expected {project_id}, got {task_project_id}")
        
        logger.info(f"Task with title '{title}' not found")
        return None
    
    def create_task(self, project_id: int, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task."""
        logger.info(f"Creating task in project {project_id}")
        return self._make_request(f"projects/{project_id}/tasks", method='PUT', data=task_data)
    
    def update_task(self, task_id: int, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing task."""
        logger.info(f"Updating task {task_id}")
        return self._make_request(f"tasks/{task_id}", method='POST', data=task_data)
    
    def add_task_label(self, task_id: int, label_id: int) -> Dict[str, Any]:
        """Add a label to a task."""
        logger.info(f"Adding label {label_id} to task {task_id}")
        return self._make_request(f"tasks/{task_id}/labels", method='PUT', data={"label_id": label_id})
    
    def add_task_relation(self, task_id: int, other_task_id: int, relation_kind: str = "related") -> Dict[str, Any]:
        """Add a relation between tasks."""
        logger.info(f"Adding relation from task {task_id} to task {other_task_id}")
        return self._make_request(f"tasks/{task_id}/relations", method='PUT', data={
            "other_task_id": other_task_id,
            "relation_kind": relation_kind
        })
    
    def close(self):
        """Close the session."""
        self.session.close()
