from pathlib import Path
import gzip
from typing import Optional

def uncompress_file(file_path: Path, dest_dir: Optional[Path]) -> Path:
    """
    Decompresses a file using zlib and returns the path of the decompressed file.
    Args:
        file_path (Path): The path of the compressed file.
        dest_dir (Optional[Path]): The directory where the decompressed file will be saved. If None, the file will be saved in the same directory as the compressed file.
    Returns:
        Path: The path of the decompressed file.
    Raises:
        FileNotFoundError: If the file does not exist.
    Examples:
        >>> file = Path("data/brdc1500.21n.gz")
        >>> uncompress_file(file)
        Path("data/brdc1500.21n")
    """
    # Ensure the file exists
    if not file_path.exists():
        raise FileNotFoundError(f"File {file_path} does not exist.")

    out_file_path = file_path.with_suffix("")
    if dest_dir is not None:
        out_file_path = dest_dir / out_file_path.name
        if not dest_dir.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with gzip.open(file_path, "rb") as f_in:
            with open(out_file_path, "wb") as f_out:
                f_out.write(f_in.read())
    except EOFError as e:
        # Optionally, remove the corrupted file
        file_path.unlink(missing_ok=True)
        return None
    
    return out_file_path

def is_gzip_file(file_path: Path) -> bool:
    """
    Check if a file is a gzip compressed file.
    Args:
        file_path (Path): The path of the file to check.
    Returns:
        bool: True if the file is gzip compressed, False otherwise.
    Examples:
        >>> file = Path("data/brdc1500.21n.gz")
        >>> is_gzip_file(file)
        True
    """
    with open(file_path, "rb") as f:
        magic_number = f.read(2)
    return magic_number == b"\x1f\x8b"

def is_corrupted_gzip(file_path: Path) -> bool:
    """
    Check if a gzip file is corrupted.
    Args:
        file_path (Path): The path of the gzip file to check.
    Returns:
        bool: True if the gzip file is corrupted, False otherwise.
    Examples:
        >>> file = Path("data/brdc1500.21n.gz")
        >>> is_corrupted_gzip(file)
        False
    """
    try:
        with gzip.open(file_path, "rb") as f:
            while f.read(1024 * 1024):
                pass
        return False
    except EOFError:
        return True

def safe_uncompress_file(file_path: Path, dest_dir: Optional[Path]) -> Optional[Path]:
    """
    Safely decompresses a gzip file, checking for corruption before decompression.
    Args:
        file_path (Path): The path of the compressed file.
        dest_dir (Optional[Path]): The directory where the decompressed file will be saved. If None, the file will be saved in the same directory as the compressed file.
    Returns:
        Optional[Path]: The path of the decompressed file, or None if the file was corrupted.
    Examples:
        >>> file = Path("data/brdc1500.21n.gz")
        >>> safe_uncompress_file(file)
        Path("data/brdc1500.21n")
    """
    if is_corrupted_gzip(file_path):
        # Optionally, remove the corrupted file
        file_path.unlink(missing_ok=True)
        return None
    return uncompress_file(file_path, dest_dir)