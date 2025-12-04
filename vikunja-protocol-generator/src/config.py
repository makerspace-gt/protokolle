"""Configuration management for Vikunja Protocol Generator."""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv


@dataclass
class Config:
    """Configuration class for Vikunja Protocol Generator."""

    vikunja_base_url: str
    vikunja_api_token: str
    meta_task_id: str
    rules_task_id: Optional[str] = None
    min_comments: int = 2
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables."""
        load_dotenv(override=True)
        
        # Required variables
        base_url = os.getenv("VIKUNJA_BASE_URL")
        api_token = os.getenv("VIKUNJA_API_TOKEN")
        task_id = os.getenv("META_TASK_ID")
        
        if not base_url:
            raise ValueError("VIKUNJA_BASE_URL environment variable is required")
        if not api_token:
            raise ValueError("VIKUNJA_API_TOKEN environment variable is required")
        if not task_id:
            raise ValueError("META_TASK_ID environment variable is required")
        
        # Optional variables with defaults
        min_comments = int(os.getenv("MIN_COMMENTS", "2"))
        rules_task_id = os.getenv("RULES_TASK_ID")

        return cls(
            vikunja_base_url=base_url.rstrip('/'),
            vikunja_api_token=api_token,
            meta_task_id=task_id,
            rules_task_id=rules_task_id,
            min_comments=min_comments
        )
    
    def validate(self) -> None:
        """Validate configuration values."""
        if not self.vikunja_base_url.startswith(('http://', 'https://')):
            raise ValueError("VIKUNJA_BASE_URL must be a valid URL")

        if self.min_comments < 0:
            raise ValueError("MIN_COMMENTS must be non-negative")

        if not self.meta_task_id.isdigit():
            raise ValueError("META_TASK_ID must be a numeric task ID")

        if self.rules_task_id and not self.rules_task_id.isdigit():
            raise ValueError("RULES_TASK_ID must be a numeric task ID")
