#!/usr/bin/env python3
"""
Vikunja Task Creator

Script to create tasks in Vikunja for protocol generation.
"""

import logging
import re
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from src.config import Config
from src.vikunja_client import VikunjaClient, VikunjaAPIError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for task creation."""
    try:
        # Load configuration
        logger.info("Loading configuration")
        config = Config.from_env()
        config.validate()
        
        # Initialize API client
        logger.info("Initializing Vikunja client")
        client = VikunjaClient(config)
        
        try:
            # Fetch all labels
            logger.info("Fetching all labels")
            labels = client.get_labels()
            
            logger.info(f"Found {len(labels)} labels:")
            for label in labels:
                logger.info(f"  - {label.get('title', 'Unknown')} (ID: {label.get('id', 'Unknown')})")
            
            # Filter labels with YYYY-MM format and sort by title
            date_pattern = re.compile(r'^\d{4}-\d{2}$')
            date_labels = [
                label for label in labels 
                if date_pattern.match(label.get('title', ''))
            ]
            date_labels.sort(key=lambda x: x.get('title', ''))
            
            logger.info(f"\nFound {len(date_labels)} labels with YYYY-MM format:")
            for label in date_labels:
                label_title = label.get('title')
                label_id = label.get('id')
                logger.info(f"\nProcessing label: {label_title} (ID: {label_id})")
                
                # Get all tasks with this label
                try:
                    tasks = client.get_tasks_by_label(label_id)
                    logger.info(f"  Found {len(tasks)} tasks with label '{label_title}':")
                    
                    for task in tasks:
                        task_title = task.get('title', 'Untitled')
                        task_id = task.get('id', 'Unknown')
                        task_done = task.get('done', False)
                        status = "✓" if task_done else "○"
                        logger.info(f"    {status} {task_title} (ID: {task_id})")
                        
                except VikunjaAPIError as e:
                    logger.error(f"  Failed to fetch tasks for label '{label_title}': {e}")
            
            # Process all date labels
            if date_labels:
                # Find "meta" and "posteventiv" labels once
                meta_label = None
                posteventiv_label = None
                for label in labels:
                    if label.get('title', '').lower() == 'meta':
                        meta_label = label
                    elif label.get('title', '').lower() == 'posteventiv':
                        posteventiv_label = label
                
                if meta_label:
                    logger.info(f"Found meta label (ID: {meta_label.get('id')})")
                else:
                    logger.warning("Meta label not found")
                    
                if posteventiv_label:
                    logger.info(f"Found posteventiv label (ID: {posteventiv_label.get('id')})")
                else:
                    logger.warning("Posteventiv label not found")
                
                project_id = 5
                
                # Preload all existing tasks for quick lookup
                logger.info("Preloading all existing tasks...")
                all_tasks = client.get_all_tasks()
                existing_tasks_by_title = {}
                for task in all_tasks:
                    if task.get('project_id') == project_id:
                        existing_tasks_by_title[task.get('title')] = task
                logger.info(f"Preloaded {len(existing_tasks_by_title)} tasks from project {project_id}")
                
                for date_label in date_labels:
                    task_title = f"Vorstandstreffen {date_label.get('title')}"
                    existing_task = existing_tasks_by_title.get(task_title)
                    
                    # Get all tasks with this label to add as related tasks
                    try:
                        related_tasks = client.get_tasks_by_label(date_label.get('id'))
                        related_task_ids = [task.get('id') for task in related_tasks]
                        
                        # Determine description based on date
                        label_date = date_label.get('title')
                        if label_date <= '2024-04':
                            description = "<p><strong>Anwesende:</strong> Jens (@CommanderRiker), Martin (@Mattn), Michael (@igami), Sarah (@Lynn), Tim (@timL)</p>"
                        elif label_date >= '2025-02':
                            description = "<p><strong>Anwesende:</strong> Klaus-Jürgen (@KayJay), Martin (@Mattn), Michael (@igami), Sarah (@Lynn), Tim (@timL)</p>"
                        else:
                            description = "<p><strong>Anwesende:</strong> Martin (@Mattn), Michael (@igami), Sarah (@Lynn), Tim (@timL)</p>"
                        
                        # Calculate dates based on label (YYYY-MM format)
                        year, month = map(int, label_date.split('-'))
                        default_due_date = datetime(year, month, 1, 19, 0)  # 1. Tag des Monats um 19:00
                        
                        # Check if task already exists and has a due_date set
                        if existing_task and existing_task.get('due_date') and existing_task.get('due_date') != "0001-01-01T00:00:00Z":
                            # Parse existing due_date and convert to Europe/Berlin timezone
                            try:
                                from dateutil import parser
                                import pytz
                                existing_due_date = parser.parse(existing_task.get('due_date'))
                                # Convert to Europe/Berlin timezone
                                berlin_tz = pytz.timezone('Europe/Berlin')
                                berlin_time = existing_due_date.astimezone(berlin_tz)
                                default_due_date = berlin_time.replace(tzinfo=None)  # Remove timezone for display
                            except:
                                pass  # Keep calculated default if parsing fails
                        
                        # Ask user for due date with default
                        print(f"\nTask: {task_title}")
                        if existing_task:
                            print(f"  (Task already exists - ID: {existing_task.get('id')})")
                        default_date_str = default_due_date.strftime("%d.%m.%Y %H:%M")
                        user_input = input(f"Due date [{default_date_str}]: ").strip()
                        
                        if user_input:
                            try:
                                # Parse flexible date/time input
                                due_date = None
                                
                                # Try various formats
                                formats_to_try = [
                                    # Full formats
                                    "%d.%m.%Y %H:%M",
                                    "%d.%m.%Y",
                                    # Short formats without year (with trailing dot)
                                    "%d.%m. %H:%M",
                                    "%d.%m.",
                                ]
                                
                                for fmt in formats_to_try:
                                    try:
                                        parsed_date = datetime.strptime(user_input, fmt)
                                        
                                        # If no year provided, use current year or default year
                                        if "%Y" not in fmt:
                                            if existing_task and existing_task.get('due_date'):
                                                # Use year from existing due_date
                                                existing_year = default_due_date.year
                                            else:
                                                # Use default year from label
                                                existing_year = default_due_date.year
                                            parsed_date = parsed_date.replace(year=existing_year)
                                        
                                        # If no time provided, use default time or existing time
                                        if "%H" not in fmt:
                                            if existing_task and existing_task.get('due_date'):
                                                # Keep existing time
                                                parsed_date = parsed_date.replace(hour=default_due_date.hour, minute=default_due_date.minute)
                                            else:
                                                # Use default 19:00
                                                parsed_date = parsed_date.replace(hour=19, minute=0)
                                        
                                        due_date = parsed_date
                                        break
                                    except ValueError:
                                        continue
                                
                                # Try time-only format (HH:MM or H:MM)
                                if due_date is None and ':' in user_input and len(user_input) <= 5:
                                    try:
                                        # Try both single and double digit hours
                                        if len(user_input.split(':')[0]) == 1:
                                            time_part = datetime.strptime(user_input, "%H:%M").time()
                                        else:
                                            time_part = datetime.strptime(user_input, "%H:%M").time()
                                        # Keep existing date, only change time
                                        due_date = default_due_date.replace(hour=time_part.hour, minute=time_part.minute)
                                    except ValueError:
                                        pass
                                
                                # Try hour-only format (H: or HH:)
                                if due_date is None and user_input.endswith(':') and len(user_input) <= 3:
                                    try:
                                        hour_str = user_input[:-1]  # Remove the ':'
                                        hour = int(hour_str)
                                        if 0 <= hour <= 23:
                                            # Keep existing date and minutes, only change hour
                                            due_date = default_due_date.replace(hour=hour)
                                    except ValueError:
                                        pass
                                
                                # Try day-only format (d.)
                                if due_date is None and user_input.endswith('.') and len(user_input) <= 3:
                                    try:
                                        day_str = user_input[:-1]  # Remove the '.'
                                        day = int(day_str)
                                        if 1 <= day <= 31:
                                            # Keep existing month, year, and time, only change day
                                            due_date = default_due_date.replace(day=day)
                                    except ValueError:
                                        pass
                                
                                if due_date is None:
                                    raise ValueError(f"Could not parse date format: {user_input}")
                                
                            except ValueError:
                                logger.warning(f"Invalid date format '{user_input}', using default")
                                due_date = default_due_date
                        else:
                            due_date = default_due_date
                        
                        # Convert due_date to UTC for API (treat input as Europe/Berlin time)
                        import pytz
                        berlin_tz = pytz.timezone('Europe/Berlin')
                        due_date_berlin = berlin_tz.localize(due_date)
                        due_date_utc = due_date_berlin.astimezone(pytz.UTC)
                        
                        # Calculate start and end dates based on Berlin time, then convert to UTC
                        start_date_berlin = due_date_berlin - relativedelta(months=1)  # Einen Monat vorher
                        end_date_berlin = due_date_berlin + relativedelta(months=1)   # Einen Monat später
                        start_date_utc = start_date_berlin.astimezone(pytz.UTC)
                        end_date_utc = end_date_berlin.astimezone(pytz.UTC)
                        
                        # Prepare labels list (meta and posteventiv labels, not the YYYY-MM date label)
                        task_label_ids = []
                        if meta_label:
                            task_label_ids.append(meta_label.get('id'))
                        if posteventiv_label:
                            task_label_ids.append(posteventiv_label.get('id'))
                        
                        # Prepare task payload (without labels and relations)
                        task_payload = {
                            "title": task_title,
                            "description": description,
                            "project_id": project_id,
                            "start_date": start_date_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
                            "due_date": due_date_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
                            "end_date": end_date_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
                        }
                        
                        logger.info(f"\n--- Processing task for label: {date_label.get('title')} ---")
                        
                        if existing_task:
                            logger.info(f"Task '{task_title}' already exists (ID: {existing_task.get('id')})")
                            
                            # Compare key fields to see if update is needed
                            needs_update = False
                            changes = []
                            # Always include all current values to prevent API from nullifying them
                            update_payload = {
                                "title": task_title, 
                                "project_id": project_id,
                                "description": existing_task.get('description', ''),
                                "start_date": existing_task.get('start_date'),
                                "due_date": existing_task.get('due_date'),
                                "end_date": existing_task.get('end_date')
                            }
                            
                            # Only update description if it's currently empty or just <p></p>
                            existing_desc = existing_task.get('description', '').strip()
                            if existing_desc in ['', '<p></p>'] and existing_task.get('description') != description:
                                needs_update = True
                                changes.append("description")
                                update_payload['description'] = description
                            
                            # Update dates - always update if user provided input or if dates are null
                            def is_null_date(date_value):
                                return not date_value or date_value == "0001-01-01T00:00:00Z"
                            
                            # Check if due_date has changed (user provided input)
                            due_date_changed = False
                            if user_input.strip():  # User provided input
                                due_date_changed = True
                            elif is_null_date(existing_task.get('due_date')):
                                due_date_changed = True
                            
                            # Update dates if due_date changed or if they are null
                            if due_date_changed or is_null_date(existing_task.get('start_date')):
                                update_payload['start_date'] = start_date_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
                                needs_update = True
                                changes.append("start_date")
                                
                            if due_date_changed or is_null_date(existing_task.get('due_date')):
                                update_payload['due_date'] = due_date_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
                                needs_update = True
                                changes.append("due_date")
                                
                            if due_date_changed or is_null_date(existing_task.get('end_date')):
                                update_payload['end_date'] = end_date_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
                                needs_update = True
                                changes.append("end_date")
                            
                            # Check if labels have changed
                            existing_labels = existing_task.get('labels', []) or []
                            existing_label_ids = set(label.get('id') for label in existing_labels)
                            new_label_ids = set(task_label_ids)
                            labels_changed = existing_label_ids != new_label_ids
                            
                            # Check if related tasks have changed
                            existing_related = existing_task.get('related_tasks', {}).get('related', [])
                            existing_related_ids = set(task.get('id') for task in existing_related)
                            new_related_ids = set(task.get('id') for task in related_tasks)
                            relations_changed = existing_related_ids != new_related_ids
                            
                            if labels_changed:
                                changes.append("labels")
                                needs_update = True
                                
                            if relations_changed:
                                changes.append("relations")
                                needs_update = True
                            
                            if needs_update:
                                logger.info(f"Task needs update - changes: {', '.join(changes)}")
                                logger.info(f"Update payload: {update_payload}")
                                response = input(f"Update task '{task_title}' (ID: {existing_task.get('id')})? [Y/n]: ")
                                if response.lower() not in ['n', 'no']:
                                    logger.info(f"Updating task with POST /tasks/{existing_task.get('id')}")
                                    update_response = client.update_task(existing_task.get('id'), update_payload)
                                    logger.info("Task updated successfully")
                                    logger.info(f"Update response: {update_response}")
                                    
                                    # Update labels if changed
                                    task_id = existing_task.get('id')
                                    if labels_changed:
                                        # Add new labels (API doesn't support removing labels, so we add missing ones)
                                        labels_to_add = new_label_ids - existing_label_ids
                                        for label_id in labels_to_add:
                                            try:
                                                client.add_task_label(task_id, label_id)
                                                logger.info(f"Added label {label_id} to task {task_id}")
                                            except Exception as e:
                                                logger.warning(f"Failed to add label {label_id}: {e}")
                                    
                                    # Update relations if changed
                                    if relations_changed:
                                        # Add new relations (API doesn't support removing relations, so we add missing ones)
                                        relations_to_add = new_related_ids - existing_related_ids
                                        for related_task_id in relations_to_add:
                                            try:
                                                client.add_task_relation(task_id, related_task_id)
                                                logger.info(f"Added relation from task {task_id} to task {related_task_id}")
                                            except Exception as e:
                                                logger.warning(f"Failed to add relation to task {related_task_id}: {e}")
                                else:
                                    logger.info("Task update skipped")
                            else:
                                logger.info("Task is already up to date - no changes needed")
                        else:
                            logger.info(f"Task '{task_title}' does not exist - creating new task")
                            logger.info(f"Task payload: {task_payload}")
                            response = input(f"Create task '{task_title}'? [Y/n]: ")
                            if response.lower() not in ['n', 'no']:
                                logger.info(f"Creating task with PUT /projects/{project_id}/tasks")
                                created_task = client.create_task(project_id, task_payload)
                                logger.info("Task created successfully")
                                logger.info(f"Created task: {created_task}")
                                
                                # Add labels via separate API calls
                                task_id = created_task.get('id')
                                if task_id:
                                    for label_id in task_label_ids:
                                        try:
                                            client.add_task_label(task_id, label_id)
                                            logger.info(f"Added label {label_id} to task {task_id}")
                                        except Exception as e:
                                            logger.warning(f"Failed to add label {label_id}: {e}")
                                    
                                    # Add relations via separate API calls
                                    for related_task in related_tasks:
                                        try:
                                            client.add_task_relation(task_id, related_task.get('id'))
                                            logger.info(f"Added relation from task {task_id} to task {related_task.get('id')}")
                                        except Exception as e:
                                            logger.warning(f"Failed to add relation to task {related_task.get('id')}: {e}")
                            else:
                                logger.info("Task creation skipped")
                        
                    except VikunjaAPIError as e:
                        logger.error(f"Failed to fetch related tasks for label '{date_label.get('title')}': {e}")
            
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
    
    return 0


if __name__ == "__main__":
    exit(main())