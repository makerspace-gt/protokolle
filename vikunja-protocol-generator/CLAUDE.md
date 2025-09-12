# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a simple Python script called "Vikunja Protocol Generator" that fetches task data from a Vikunja instance via its REST API and generates German meeting protocols using Jinja2 templates. It's designed for makerspace protocol generation.

## Development Commands

### Running the Application
```bash
# Generate protocol from meta task
python vikunja2md.py

# Install dependencies
pip install -r requirements.txt
```

### Environment Setup
The application requires a `.env` file with the following variables:
- `VIKUNJA_BASE_URL`: Base URL of your Vikunja instance
- `VIKUNJA_API_TOKEN`: API token for authentication  
- `META_TASK_ID`: ID of the meta task containing related agenda items
- `MIN_COMMENTS`: Minimum number of comments to include (default: 2)

## Architecture Overview

This is a single-file application with straightforward execution flow:

### Core Script: vikunja2md.py
1. **Environment Loading**: Loads configuration from `.env` file using python-dotenv
2. **API Calls**: Makes direct HTTP requests to Vikunja API endpoints:
   - Fetches all labels via `/api/v1/labels`
   - Fetches all projects via `/api/v1/projects` 
   - Fetches meta task via `/api/v1/tasks/{task_id}`
   - Fetches comments for each related task via `/api/v1/tasks/{task_id}/comments`
3. **Data Assembly**: Combines API responses into a single data structure with metadata
4. **Template Processing**: Uses Jinja2 to render `vikunja2md.md.j2` template
5. **Output**: Writes rendered markdown to `vikunja2md.md`

### Custom Jinja2 Filters
- `format_date`: Formats ISO date strings to German format (%d.%m.%Y %H:%M)
- `filter_comments_with_minimum`: Filters comments by date range with minimum comment logic

### Template System
The Jinja2 template (`vikunja2md.md.j2`) generates a German protocol with:
- Meeting title and date from meta task
- Attendee list from task assignees
- Agenda items from related tasks
- Task descriptions and filtered comments
- Links back to Vikunja tasks

### Data Flow
1. Load environment variables from `.env`
2. Fetch labels, projects, and meta task data from Vikunja API
3. For each related task, fetch and attach comments
4. Create output data structure with API responses + metadata
5. Save raw JSON data to `vikunja2md.json`
6. Render Jinja2 template with assembled data
7. Generate output path based on meta task due date and title
8. Create year directory structure (`../{year}/`) if needed
9. Write final markdown protocol to `../{year}/{YYYY-MM-DD} - {title}.md`

## Key Implementation Details

### Comment Filtering Logic
The `filter_comments_with_minimum` function implements sophisticated comment selection:
- Filters comments within the specified date range (from meta task start_date to end_date)
- If fewer than `MIN_COMMENTS` found in range, includes the last `MIN_COMMENTS` before end_date
- Handles ISO date parsing with timezone conversion
- Gracefully handles date parsing errors

### API Authentication
All API requests use Bearer token authentication with the `VIKUNJA_API_TOKEN`

### File Outputs
- `vikunja2md.json`: Raw API data dump for debugging/inspection  
- `../{year}/{YYYY-MM-DD} - {title}.md`: Final rendered German protocol (organized by year)
- Fallback to `vikunja2md.md` if no due date is available

### Output Path Generation
The script automatically creates an organized file structure:
- Extracts year and date from meta task's `due_date` field
- Sanitizes task title for use in filename (removes invalid characters)
- Creates year directory in parent folder (`../{year}/`)
- Saves protocol with format: `{YYYY-MM-DD} - {sanitized_title}.md`
