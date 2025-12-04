"""Jinja2 filters and formatting utilities for Vikunja Protocol Generator."""

import base64
import logging
import re
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import requests

logger = logging.getLogger(__name__)

DEFAULT_DATE_FORMAT = '%d.%m.%Y %H:%M'
MIN_COMMENTS_DEFAULT = 2


def format_date(date_string: Optional[str], format_str: str = DEFAULT_DATE_FORMAT) -> str:
    """
    Format ISO date string to German format.
    
    Args:
        date_string: ISO format date string
        format_str: strftime format string
        
    Returns:
        Formatted date string or original string if parsing fails
    """
    if not date_string:
        return ""
    
    try:
        date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return date_obj.strftime(format_str)
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to parse date '{date_string}': {e}")
        return str(date_string) if date_string else ""


def _preprocess_html_lists(html_content: str) -> str:
    """Preprocess HTML content to handle task lists and regular lists."""
    # Convert Vikunja checklist HTML to regular list HTML
    html_content = re.sub(r'<ul data-type="taskList">', '<ul>', html_content)
    html_content = re.sub(r'<li[^>]*data-checked="false" data-type="taskItem"[^>]*>', '<li>[ ] ', html_content)
    html_content = re.sub(r'<li[^>]*data-checked="true" data-type="taskItem"[^>]*>', '<li>[x] ', html_content)
    html_content = re.sub(r'<label><input[^>]*><span></span></label>', '', html_content)
    
    return html_content


def _clean_list_paragraphs(html_content: str) -> str:
    """Clean paragraph and div tags within lists to improve markdown conversion."""
    if not re.search(r'<(ul|ol)', html_content):
        return html_content
        
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Process all ul/ol lists
    for lst in soup.find_all(["ul", "ol"]):
        # Step 1: Replace </p><p> with </p><br><p> within list items
        for tag in lst.find_all(["p", "div"]):
            tag_str = str(tag)
            tag_str = re.sub(r'</p><p>', '</p><br><p>', tag_str)
            new_soup = BeautifulSoup(tag_str, "html.parser")
            tag.replace_with(new_soup)
        
        # Step 2: Remove p and div tags while keeping content
        for tag in lst.find_all(["p", "div"]):
            tag.unwrap()
    
    return str(soup)


def _convert_with_pandoc(html_content: str) -> str:
    """Convert HTML to GitHub Flavored Markdown using pandoc."""
    try:
        result = subprocess.run(
            ['pandoc', '--from=html', '--to=gfm', '--wrap=none'],
            input=html_content,
            text=True,
            capture_output=True,
            check=True,
            timeout=30
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Pandoc conversion failed: {e}")
        raise RuntimeError(f"Pandoc conversion failed: {e}")
    except subprocess.TimeoutExpired:
        logger.error("Pandoc conversion timed out")
        raise RuntimeError("Pandoc conversion timed out")
    except FileNotFoundError:
        logger.error("Pandoc not found. Please install pandoc.")
        raise RuntimeError("Pandoc not found. Please install pandoc.")


def _postprocess_markdown(markdown_content: str) -> str:
    """Post-process markdown to clean up links and checkboxes."""
    # Convert HTML links to cleaner format
    # First, handle links where the text is the same as the URL
    markdown_content = re.sub(r'<a href="([^"]*)"[^>]*>\1</a>', r'<\1>', markdown_content)
    # Then, handle links where the text differs from the URL
    markdown_content = re.sub(r'<a href="([^"]*)"[^>]*>([^<]*)</a>', r'[\2](\1)', markdown_content)

    # Fix escaped checkboxes
    markdown_content = re.sub(r"\\\[(x| )\\\]", r"[\1]", markdown_content)

    return markdown_content


def _download_image_as_base64(url: str, api_token: str) -> Optional[str]:
    """Download an image and convert it to base64."""
    try:
        headers = {'Authorization': f'Bearer {api_token}'}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Get content type from response
        content_type = response.headers.get('Content-Type', 'image/png')

        # Encode to base64
        base64_data = base64.b64encode(response.content).decode('utf-8')

        return f"data:{content_type};base64,{base64_data}"
    except Exception as e:
        logger.error(f"Failed to download image from {url}: {e}")
        return None


def embed_images_as_base64(markdown_content: str, base_url: str, api_token: str) -> str:
    """
    Find images in markdown and embed them as base64.

    Args:
        markdown_content: Markdown content with image tags
        base_url: Vikunja base URL
        api_token: API token for authentication

    Returns:
        Markdown content with embedded base64 images
    """
    if not markdown_content:
        return ""

    # Find all img tags with data-src attribute (Vikunja format)
    img_pattern = r'<img[^>]*data-src="([^"]*)"[^>]*/?>'

    def replace_image(match):
        img_url = match.group(1)

        # Make URL absolute if needed
        if img_url.startswith('/'):
            img_url = f"{base_url}{img_url}"
        elif not img_url.startswith('http'):
            img_url = f"{base_url}/{img_url}"

        # Download and convert to base64
        base64_url = _download_image_as_base64(img_url, api_token)

        if base64_url:
            return f'<img src="{base64_url}" />'
        else:
            # Keep original if download failed
            return match.group(0)

    return re.sub(img_pattern, replace_image, markdown_content)


def vikunja_to_gfm(html_content: Optional[str], base_url: str = None, api_token: str = None) -> str:
    """
    Convert Vikunja HTML content to GitHub Flavored Markdown.

    Args:
        html_content: HTML content from Vikunja
        base_url: Optional Vikunja base URL for embedding images
        api_token: Optional API token for downloading images

    Returns:
        Converted markdown content
    """
    if not html_content:
        return ""

    try:
        # Preprocessing steps
        html_content = _preprocess_html_lists(html_content)
        html_content = _clean_list_paragraphs(html_content)

        # Convert with pandoc
        markdown_content = _convert_with_pandoc(html_content)

        # Post-processing
        markdown_content = _postprocess_markdown(markdown_content)

        # Embed images as base64 if credentials provided
        if base_url and api_token:
            markdown_content = embed_images_as_base64(markdown_content, base_url, api_token)

        return markdown_content

    except Exception as e:
        logger.error(f"HTML to markdown conversion failed: {e}")
        return html_content  # Return original content as fallback


def _parse_date_safely(date_string: str) -> Optional[datetime]:
    """Safely parse ISO date string."""
    try:
        return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        return None


def _filter_comments_by_date_range(comments: List[Dict[str, Any]], 
                                 start_date_obj: datetime, 
                                 end_date_obj: datetime) -> List[Dict[str, Any]]:
    """Filter comments within the specified date range."""
    filtered_comments = []
    
    for comment in comments:
        comment_date = _parse_date_safely(comment.get('created', ''))
        if comment_date and start_date_obj <= comment_date <= end_date_obj:
            filtered_comments.append(comment)
    
    return filtered_comments


def _get_fallback_comments(comments: List[Dict[str, Any]], 
                          end_date_obj: datetime, 
                          min_comments: int) -> List[Dict[str, Any]]:
    """Get fallback comments when not enough are in the date range."""
    before_end_comments = []
    
    for comment in comments:
        comment_date = _parse_date_safely(comment.get('created', ''))
        if comment_date and comment_date <= end_date_obj:
            before_end_comments.append(comment)
    
    # Return last min_comments before end date
    return before_end_comments[-min_comments:] if len(before_end_comments) >= min_comments else before_end_comments


def filter_comments_with_minimum(comments: List[Dict[str, Any]], 
                                start_date: str, 
                                end_date: str, 
                                min_comments: int = MIN_COMMENTS_DEFAULT) -> List[Dict[str, Any]]:
    """
    Filter comments with configurable minimum comments logic.
    
    Args:
        comments: List of comment dictionaries
        start_date: ISO start date string
        end_date: ISO end date string  
        min_comments: Minimum number of comments to include
        
    Returns:
        Filtered list of comments
    """
    if not comments:
        return []
    
    # Parse date boundaries
    start_date_obj = _parse_date_safely(start_date)
    end_date_obj = _parse_date_safely(end_date)
    
    if not start_date_obj or not end_date_obj:
        logger.warning(f"Failed to parse date range: {start_date} - {end_date}")
        return comments[-min_comments:] if len(comments) >= min_comments else comments
    
    # Filter comments in date range
    filtered_comments = _filter_comments_by_date_range(comments, start_date_obj, end_date_obj)
    
    # If less than min_comments in range, get fallback comments
    if len(filtered_comments) < min_comments:
        logger.debug(f"Only {len(filtered_comments)} comments in range, getting fallback comments")
        return _get_fallback_comments(comments, end_date_obj, min_comments)
    
    return filtered_comments
