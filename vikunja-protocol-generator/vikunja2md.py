#!/usr/bin/env python3

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
import html2text

load_dotenv(override=True)

base_url = os.getenv("VIKUNJA_BASE_URL")
api_token = os.getenv("VIKUNJA_API_TOKEN")
task_id = os.getenv("META_TASK_ID")
min_comments = int(os.getenv("MIN_COMMENTS", "2"))

labels = requests.get(
    f"{base_url}/api/v1/labels",
    headers={"Authorization": f"Bearer {api_token}"}
)

projects = requests.get(
    f"{base_url}/api/v1/projects",
    headers={"Authorization": f"Bearer {api_token}"}
)

meta = requests.get(
    f"{base_url}/api/v1/tasks/{task_id}",
    headers={"Authorization": f"Bearer {api_token}"}
)

# Fetch comments for each related task
meta_json = meta.json()
if meta_json.get("related_tasks") and meta_json["related_tasks"].get("related"):
    for task in meta_json["related_tasks"]["related"]:
        task_id_for_comments = task["id"]
        comments_response = requests.get(
            f"{base_url}/api/v1/tasks/{task_id_for_comments}/comments",
            headers={"Authorization": f"Bearer {api_token}"}
        )
        task["comments"] = comments_response.json() if comments_response.status_code == 200 else []

output = {
    "labels": labels.json(),
    "projects": projects.json(), 
    "meta": meta_json,
    "now": datetime.now().isoformat(),
    "base_url": base_url,
    "min_comments": min_comments
}

with open("vikunja2md.json", "w") as f:
    json.dump(output, f, indent=2)

# Format date filter
def format_date(date_string, format_str='%d.%m.%Y %H:%M'):
    if not date_string:
        return ""
    try:
        date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return date_obj.strftime(format_str)
    except:
        return date_string

# Preprocess Vikunja taskLists for proper GFM conversion
def preprocess_vikunja_tasklists(html_content):
    if not html_content or 'data-type="taskList"' not in html_content:
        return html_content
    
    import re
    
    # Replace Vikunja taskList structure with standard HTML that converts to GFM checkboxes
    def replace_tasklist(match):
        tasklist_content = match.group(1)
        
        # Find all taskItems within this taskList
        taskitem_pattern = r'<li data-checked="(true|false)" data-type="taskItem">.*?<label>.*?<input type="checkbox"[^>]*>.*?<span></span></label><div>(.*?)</div></li>'
        
        def replace_taskitem(item_match):
            is_checked = item_match.group(1) == 'true'
            content = item_match.group(2)
            
            # Handle nested taskLists recursively
            content = preprocess_vikunja_tasklists(content)
            
            # Convert to simple list item with GFM checkbox syntax
            checkbox = '[x]' if is_checked else '[ ]'
            return f'<li>{checkbox} {content}</li>'
        
        # Replace all taskItems in this taskList
        converted_items = re.sub(taskitem_pattern, replace_taskitem, tasklist_content, flags=re.DOTALL)
        
        # Return as regular unordered list
        return f'<ul>{converted_items}</ul>'
    
    # Replace all taskLists
    tasklist_pattern = r'<ul data-type="taskList">(.*?)</ul>'
    result = re.sub(tasklist_pattern, replace_tasklist, html_content, flags=re.DOTALL)
    
    return result

# Post-process markdown to clean up list formatting
def clean_list_formatting(markdown_text):
    if not markdown_text:
        return ""
    
    import re
    
    # Split into lines for processing
    lines = markdown_text.split('\n')
    cleaned_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        cleaned_lines.append(line)
        
        # If current line is a list item (starts with * or -)
        if re.match(r'^\s*[\*\-\+]\s', line):
            # Look ahead for blank lines
            j = i + 1
            blank_count = 0
            
            # Count consecutive blank lines after list item
            while j < len(lines) and lines[j].strip() == '':
                blank_count += 1
                j += 1
            
            # Check what follows after the blank lines
            if j < len(lines):
                next_line = lines[j]
                
                # If next non-empty line is also a list item at same level, 
                # reduce blank lines to maximum of 1
                if re.match(r'^\s*[\*\-\+]\s', next_line):
                    # Add at most 1 blank line between list items
                    if blank_count > 1:
                        cleaned_lines.append('')  # Add single blank line
                        i = j - 1  # Skip the extra blank lines
                    else:
                        i += blank_count  # Keep existing spacing if <= 1
                else:
                    # Next line is not a list item - end of list
                    # Ensure there's exactly one blank line after the list
                    if blank_count == 0:
                        cleaned_lines.append('')  # Add blank line after list
                    elif blank_count > 1:
                        cleaned_lines.append('')  # Reduce to single blank line
                        i = j - 1  # Skip extra blank lines
                    else:
                        i += blank_count  # Keep existing single blank line
            else:
                # End of text - keep existing spacing
                i += blank_count
        
        i += 1
    
    return '\n'.join(cleaned_lines)

# HTML to Markdown converter
def vikunja_to_gfm(html_content):
    if not html_content:
        return ""
    
    # First preprocess Vikunja taskLists
    preprocessed = preprocess_vikunja_tasklists(html_content)
    
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0  # Don't wrap lines
    h.unicode_snob = True
    h.escape_snob = False
    
    markdown = h.handle(preprocessed).strip()
    
    # Clean up list formatting
    return clean_list_formatting(markdown)

# Filter comments with configurable minimum comments logic
def filter_comments_with_minimum(comments, start_date, end_date, min_comments=2):
    if not comments:
        return []
    
    try:
        start_date_obj = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_date_obj = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except:
        return comments[-min_comments:] if len(comments) >= min_comments else comments
    
    # Filter comments in date range
    filtered_comments = []
    for comment in comments:
        try:
            comment_date = datetime.fromisoformat(comment['created'].replace('Z', '+00:00'))
            if start_date_obj <= comment_date <= end_date_obj:
                filtered_comments.append(comment)
        except:
            continue
    
    # If less than min_comments in range, get last min_comments before end_date
    if len(filtered_comments) < min_comments:
        before_end_comments = []
        for comment in comments:
            try:
                comment_date = datetime.fromisoformat(comment['created'].replace('Z', '+00:00'))
                if comment_date <= end_date_obj:
                    before_end_comments.append(comment)
            except:
                continue
        return before_end_comments[-min_comments:] if len(before_end_comments) >= min_comments else before_end_comments
    
    return filtered_comments

# Template rendering
env = Environment(loader=FileSystemLoader('.'))
env.filters['format_date'] = format_date
env.filters['filter_comments_with_minimum'] = filter_comments_with_minimum
env.filters['vikunja_to_gfm'] = vikunja_to_gfm
template = env.get_template('vikunja2md.md.j2')

rendered_markdown = template.render(**output)

# Create output path based on due date and title
import re
due_date = meta_json.get('due_date', '')
title = meta_json.get('title', 'protocol')

if due_date:
    year = format_date(due_date, '%Y')
    date_str = format_date(due_date, '%Y-%m-%d')
    
    # Sanitize title for filename
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
    
    # Create directory structure
    output_dir = f"../{year}"
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = f"{output_dir}/{date_str} - {safe_title}.md"
else:
    output_path = "vikunja2md.md"

with open(output_path, "w") as f:
    f.write(rendered_markdown)
    
print(f"Protocol saved to: {output_path}")
