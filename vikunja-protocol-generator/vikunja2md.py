#!/usr/bin/env python3

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv(override=True)

base_url = os.getenv("VIKUNJA_BASE_URL")
api_token = os.getenv("VIKUNJA_API_TOKEN")
task_id = os.getenv("META_TASK_ID")

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
    "base_url": base_url
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

# Template rendering
env = Environment(loader=FileSystemLoader('.'))
env.filters['format_date'] = format_date
template = env.get_template('vikunja2md.md.j2')

rendered_markdown = template.render(**output)

with open("vikunja2md.md", "w") as f:
    f.write(rendered_markdown)
