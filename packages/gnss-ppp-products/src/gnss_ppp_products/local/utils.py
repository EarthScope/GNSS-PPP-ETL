from calendar import c
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def check_file(path: Path) -> bool:
    """Check if a file exists and is non-empty."""
    check_1 = path.stat().st_size > 0
    check_2 = False
    try:
        with open(path,"r+") as f:
            check_2 = f.readable()
    except Exception as e:
        logger.error(f"Error checking file {path}: {e}")
    return check_1 and check_2