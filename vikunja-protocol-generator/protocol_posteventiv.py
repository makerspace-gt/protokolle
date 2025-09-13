#!/usr/bin/env python3
"""
Protocol Post-Eventiv Generator

Script to generate post-event protocols for all tasks with the "meta" label
using the makerspace_protocol_template_posteventiv.md.j2 template.

This script finds all tasks with the "meta" label and calls the vikunja_protocol.py
script for each task to generate individual protocols.
"""

import logging
import subprocess
import sys
from pathlib import Path
from src.config import Config
from src.vikunja_client import VikunjaClient, VikunjaAPIError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for post-eventiv protocol generation."""
    try:
        # Load configuration
        logger.info("Loading configuration")
        config = Config.from_env()
        config.validate()
        
        # Initialize API client
        logger.info("Initializing Vikunja client")
        client = VikunjaClient(config)
        
        try:
            # Find meta label
            logger.info("Fetching all labels")
            labels = client.get_labels()
            
            meta_label = None
            for label in labels:
                if label.get('title', '').lower() == 'posteventiv':
                    meta_label = label
                    break
            
            if not meta_label:
                logger.error("Meta label not found")
                return 1
            
            logger.info(f"Found meta label (ID: {meta_label.get('id')})")
            
            # Get all tasks with meta label
            logger.info("Fetching tasks with meta label")
            meta_tasks = client.get_tasks_by_label(meta_label.get('id'))
            logger.info(f"Found {len(meta_tasks)} tasks with meta label")
            
            # Check if post-eventiv template exists
            template_path = "templates/makerspace_protocol_template_posteventiv.md.j2"
            if not Path(template_path).exists():
                logger.error(f"Post-eventiv template not found: {template_path}")
                logger.info("Please create the template file first")
                return 1
            
            # Process each meta task
            success_count = 0
            error_count = 0
            
            for task in meta_tasks:
                task_id = task.get('id')
                task_title = task.get('title', 'Unknown')
                
                logger.info(f"Processing task: {task_title} (ID: {task_id})")
                
                try:
                    # Call vikunja_protocol.py with specific task ID and template
                    result = subprocess.run([
                        sys.executable, "vikunja_protocol.py",
                        "--task-id", str(task_id),
                        "--template", template_path
                    ], check=True, capture_output=True, text=True)
                    
                    logger.info(f"Successfully generated protocol for task {task_id}")
                    success_count += 1
                    
                    # Log output from subprocess if needed
                    if result.stdout:
                        logger.debug(f"Protocol script output: {result.stdout}")
                    
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to generate protocol for task {task_id}: {e}")
                    if e.stderr:
                        logger.error(f"Error output: {e.stderr}")
                    error_count += 1
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error processing task {task_id}: {e}")
                    error_count += 1
                    continue
            
            # Summary
            total_tasks = len(meta_tasks)
            logger.info(f"Protocol generation completed:")
            logger.info(f"  Total tasks: {total_tasks}")
            logger.info(f"  Successful: {success_count}")
            logger.info(f"  Failed: {error_count}")
            
            return 0 if error_count == 0 else 1
            
        finally:
            client.close()
            
    except (ValueError, VikunjaAPIError) as e:
        logger.error(f"Application error: {e}")
        return 1
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())