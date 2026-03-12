import re
from typing import Optional
from requests import get, Response
from functools import lru_cache

def extract_filenames_from_html(html: str) -> list[str]:
    """
    Extract filenames from an Apache/nginx HTML directory listing.

    Parses <a href="filename"> tags to get file names.
    """
    # Match href attributes that look like filenames (not directories or parent links)
    pattern = r'<a href="([^"?/][^"?]*)"'
    matches = re.findall(pattern, html)
    # Filter out non-file entries and decode URL encoding
    from urllib.parse import unquote

    filenames = []
    for match in matches:
        decoded = unquote(match)
        # Skip parent directory links and query strings
        if decoded and not decoded.startswith("?") and not decoded.endswith("/"):
            filenames.append(decoded)
    return filenames

@lru_cache(maxsize=128)
def http_list_directory(
    server: str,
    directory: str) -> Optional[str]:

    try:
        response:Response = get(f"{server}/{directory}",timeout=30)
        response.raise_for_status()
        text = response.text
        return text
    
    except Exception as e:
        print(f"Error listing HTTP directory {server}/{directory}: {e}")
        return None
