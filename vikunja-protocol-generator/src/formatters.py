"""Jinja2 filters and formatting utilities for Vikunja Protocol Generator."""

import logging
import re
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

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


def _convert_html_tags_in_text(text: str) -> str:
    """Convert common HTML tags to markdown within link text."""
    # Convert strong/b to markdown bold
    text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text)
    text = re.sub(r'<b>(.*?)</b>', r'**\1**', text)
    # Convert em/i to markdown italic
    text = re.sub(r'<em>(.*?)</em>', r'*\1*', text)
    text = re.sub(r'<i>(.*?)</i>', r'*\1*', text)
    # Convert code to markdown code
    text = re.sub(r'<code>(.*?)</code>', r'`\1`', text)
    return text


def _postprocess_markdown(markdown_content: str) -> str:
    """Post-process markdown to clean up links and checkboxes."""
    # Convert HTML links to cleaner format
    # First, handle links where the text is the same as the URL
    markdown_content = re.sub(r'<a href="([^"]*)"[^>]*>\1</a>', r'<\1>', markdown_content)

    # Then, handle links where the text differs from the URL (including nested HTML tags)
    def convert_link(match):
        url = match.group(1)
        text = match.group(2)
        # Convert HTML tags in link text to markdown
        text = _convert_html_tags_in_text(text)
        return f'[{text}]({url})'

    markdown_content = re.sub(r'<a href="([^"]*)"[^>]*>(.*?)</a>', convert_link, markdown_content)

    # Fix escaped checkboxes
    markdown_content = re.sub(r"\\\[(x| )\\\]", r"[\1]", markdown_content)

    return markdown_content.strip()


def vikunja_to_gfm(html_content: Optional[str]) -> str:
    """
    Convert Vikunja HTML content to GitHub Flavored Markdown.
    
    Args:
        html_content: HTML content from Vikunja
        
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
