import re
from typing import List, Optional
from anyio import Path
from requests import get, Response
from functools import lru_cache
from urllib.parse import unquote

def http_can_connect(httpserver, timeout: int = 10) -> bool:
    try:
        response = get(httpserver, timeout=timeout)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Failed to connect to HTTP server {httpserver} | {e}")
        return False
    
def extract_filenames_from_html(html: str) -> list[str]:
    """
    Extract filenames from an Apache/nginx HTML directory listing.

    Parses <a href="filename"> tags to get file names.
    """
    # Match href attributes that look like filenames (not directories or parent links)
    pattern = r'<a href="([^"?/][^"?]*)"'
    matches = re.findall(pattern, html)
    # Filter out non-file entries and decode URL encoding
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

def http_protocol(
    httpserver:str,
    directory:str,
    filequery:str
) -> List[str]:
    out = []
    listing: Optional[str] = http_list_directory(
        server=httpserver,
        directory=directory
    )
    if listing is None:
        return out
    for filename in extract_filenames_from_html(listing):
        if re.match(filequery, filename):
    
            print(f"Best match for {filequery}: {filename}")
            out.append(filename)
    return out

def http_get_file(
    httpserver:str,
    directory:str,
    filename:str,
    dest_dir:Optional[Path]=None,
    timeout:int=60
) -> Optional[bytes]:
    try:
        with get(f"{httpserver}/{directory}/{filename}",timeout=timeout,stream=True) as response:
            response.raise_for_status()
            if dest_dir is not None:
                dest_dir.mkdir(parents=True, exist_ok=True)
                file_path = dest_dir / filename
            else:
                file_path = filename
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
    except Exception as e:
        print(f"Error fetching HTTP file {httpserver}/{directory}/{filename}: {e}")
        return None
