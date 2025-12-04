#!/usr/bin/env python3
"""
Vikunja Protocol Generator - Refactored Version

Fetches task data from a Vikunja instance via REST API and generates 
German meeting protocols using Jinja2 templates.
"""

import argparse
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from jinja2 import Environment, FileSystemLoader

from src.config import Config
from src.vikunja_client import VikunjaClient, VikunjaAPIError
from src.formatters import format_date, filter_comments_with_minimum, vikunja_to_gfm, embed_images_as_base64
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
FALLBACK_OUTPUT_FILENAME = "vikunja2md.md"
DEFAULT_TEMPLATE_FILENAME = "templates/makerspace_protocol_template.md.j2"
INVALID_FILENAME_CHARS = r'[<>:"/\\|?*]'
FILENAME_REPLACEMENT = '_'


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters."""
    return re.sub(INVALID_FILENAME_CHARS, FILENAME_REPLACEMENT, filename)


def create_output_path(due_date: str, title: str) -> str:
    """Create output path based on due date and title."""
    if not due_date:
        return FALLBACK_OUTPUT_FILENAME

    try:
        year = format_date(due_date, '%Y')
        date_str = format_date(due_date, '%Y-%m-%d')
        safe_title = sanitize_filename(title)

        # Create directory structure
        output_dir = Path(f"../{year}")
        output_dir.mkdir(exist_ok=True)

        return str(output_dir / f"{date_str} - {safe_title}.md")

    except Exception as e:
        logger.warning(f"Failed to create path from due date '{due_date}': {e}")
        return FALLBACK_OUTPUT_FILENAME


def collect_mentions(meta_task: Dict[str, Any]) -> list:
    """
    Collect all @mentions from all comments in related tasks.

    Returns a sorted list of unique user dictionaries that were mentioned.
    """
    mentioned_usernames = set()
    user_pool = {}

    # Build user pool from assignees and comment authors
    if meta_task.get('assignees'):
        for user in meta_task['assignees']:
            username = user.get('username', '').lower()
            if username:
                user_pool[username] = user

    if meta_task.get('related_tasks') and meta_task['related_tasks'].get('related'):
        for task in meta_task['related_tasks']['related']:
            # Add task assignees
            if task.get('assignees'):
                for user in task['assignees']:
                    username = user.get('username', '').lower()
                    if username:
                        user_pool[username] = user

            # Add comment authors and extract mentions
            if task.get('comments'):
                for comment in task['comments']:
                    if comment.get('author'):
                        author = comment['author']
                        username = author.get('username', '').lower()
                        if username:
                            user_pool[username] = author

                    # Extract @mentions from comment HTML
                    comment_html = comment.get('comment', '')
                    if comment_html:
                        # Find all @username patterns
                        mentions = re.findall(r'@([a-zA-Z0-9_-]+)', comment_html)
                        for mention in mentions:
                            mentioned_usernames.add(mention.lower())

    # Build result list with user objects for mentioned usernames
    result = []
    for username in sorted(mentioned_usernames):
        if username in user_pool:
            result.append(user_pool[username])

    return result




def setup_jinja_environment(config: Config) -> Environment:
    """Set up Jinja2 environment with custom filters."""
    env = Environment(loader=FileSystemLoader('.'))
    env.filters['format_date'] = format_date
    env.filters['filter_comments_with_minimum'] = filter_comments_with_minimum

    # Create a closure for vikunja_to_gfm that includes config for image embedding
    def vikunja_to_gfm_filter(html_content: str) -> str:
        return vikunja_to_gfm(html_content, config.vikunja_base_url, config.vikunja_api_token)

    env.filters['vikunja_to_gfm'] = vikunja_to_gfm_filter

    # Create a closure for embed_images_as_base64 that includes config
    def embed_images_filter(markdown_content: str) -> str:
        return embed_images_as_base64(markdown_content, config.vikunja_base_url, config.vikunja_api_token)

    env.filters['embed_images'] = embed_images_filter
    return env


def render_template(template_env: Environment, template_filename: str, data: Dict[str, Any]) -> str:
    """Render the protocol template with data."""
    try:
        template = template_env.get_template(template_filename)
        return template.render(**data)
    except Exception as e:
        logger.error(f"Template rendering failed: {e}")
        raise RuntimeError(f"Template rendering failed: {e}")


def save_protocol(content: str, output_path: str) -> None:
    """Save the rendered protocol to file."""
    try:
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Protocol saved to: {output_path}")
    except Exception as e:
        logger.error(f"Failed to save protocol to {output_path}: {e}")
        raise


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate protocol from Vikunja task data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python vikunja_protocol.py                                    # Use META_TASK_ID from .env
  python vikunja_protocol.py --task-id 298                     # Use specific task ID
  python vikunja_protocol.py --template custom_template.md.j2  # Use custom template
  python vikunja_protocol.py --task-id 298 --template templates/posteventiv.md.j2
        """
    )
    
    parser.add_argument(
        '--task-id',
        type=int,
        help='Task ID to generate protocol for (overrides META_TASK_ID from .env)'
    )
    
    parser.add_argument(
        '--template',
        type=str,
        default=DEFAULT_TEMPLATE_FILENAME,
        help=f'Template file to use (default: {DEFAULT_TEMPLATE_FILENAME})'
    )
    
    return parser.parse_args()


def main():
    """Main application entry point."""
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Load and validate configuration
        logger.info("Loading configuration")
        config = Config.from_env()
        
        # Override task ID if provided via command line
        if args.task_id:
            config.meta_task_id = str(args.task_id)
            logger.info(f"Using task ID from command line: {args.task_id}")
        
        config.validate()
        
        # Initialize API client
        logger.info("Initializing Vikunja client")
        client = VikunjaClient(config)
        
        try:
            # Fetch data from Vikunja API
            logger.info(f"Fetching data from Vikunja API for task {config.meta_task_id}")
            labels = client.get_labels()
            projects = client.get_projects()
            meta_task = client.get_meta_task_with_comments()

            # Fetch rules task if configured
            rules_task = None
            if config.rules_task_id:
                logger.info(f"Fetching rules task {config.rules_task_id}")
                rules_task = client.get_task(config.rules_task_id)

            # Collect all mentions from comments
            logger.info("Collecting mentions from comments")
            mentions = collect_mentions(meta_task)

            # Prepare output data structure
            output_data = {
                "labels": labels,
                "projects": projects,
                "meta": meta_task,
                "rules": rules_task,
                "mentions": mentions,
                "now": datetime.now().isoformat(),
                "base_url": config.vikunja_base_url,
                "min_comments": config.min_comments
            }
            
            # Set up template environment and render
            logger.info(f"Rendering protocol template: {args.template}")
            template_env = setup_jinja_environment(config)
            rendered_content = render_template(template_env, args.template, output_data)
            
            # Create output path and save protocol
            output_path = create_output_path(
                meta_task.get('due_date', ''),
                meta_task.get('title', 'protocol')
            )
            save_protocol(rendered_content, output_path)
            
            logger.info("Protocol generation completed successfully")
            
        finally:
            client.close()
            
    except (ValueError, VikunjaAPIError, RuntimeError) as e:
        logger.error(f"Application error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
