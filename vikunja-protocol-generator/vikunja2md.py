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

# HTML to Markdown converter
def vikunja_to_gfm(html_content):
    if not html_content:
        return ""
    
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.body_width = 0  # Don't wrap lines
    h.unicode_snob = True
    h.escape_snob = False
    
    return h.handle(html_content).strip()

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
