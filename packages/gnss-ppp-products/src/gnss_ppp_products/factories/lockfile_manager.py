import hashlib
from pathlib import Path
import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple

def _hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"

class LockProductAlternative(BaseModel):
    """An alternative (mirror / fallback) source for a locked product."""

    url: str = Field(..., description="Absolute URL to the alternative resource.")


class LockProduct(BaseModel):
    """A single resolved product entry in the lockfile."""

    name: str
    description: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(), description="ISO 8601 timestamp of when the product was locked.")
    # Primary source
    url: str = Field(..., description="Absolute URL to the primary resource.")
    hash: str = Field("", description="Hash of the resource for integrity verification.")
    size: Optional[int] = Field(None, description="Size of the resource in bytes.")

    # Relative directory template for local layout, e.g. "products/{year}/orbit/"
    sink: str = Field("", description="Sink Path")

    alternatives: List[LockProductAlternative] = Field(default_factory=list, description="List of alternative sources for the product.")

def validate_lock_product(product: LockProduct) -> bool:
    '''
    validate a LockProduct by checking if the sink path exists and if the hash of the file at the sink path matches the expected hash.
    '''
    sink_path = Path(product.sink)
    if not sink_path.exists():
        return False
    if product.hash:
        actual_hash = _hash_file(sink_path)
        if actual_hash != product.hash:
            return False
    return True

def build_lock_product(
        sink: Path|str,
        url: str,
        name: str = "",
        description: str = "",
        alternative_urls: Optional[List[str]] = None
) -> LockProduct:
    sink_path = Path(sink)
    if not sink_path.exists():
        raise FileNotFoundError(f"Sink path does not exist: {sink_path}")
    hash_value = _hash_file(sink_path)
    size = sink_path.stat().st_size
    return LockProduct(
        name=name,
        description=description,
        url=url,
        sink=str(sink_path),
        hash=hash_value,
        size=size,
        alternatives=[LockProductAlternative(url=alt_url) for alt_url in (alternative_urls or [])]
    )

def get_lock_product_path(sink: Path|str) -> Path:
    '''
    Get the path to the locked product from the sink path.
    '''
    sink = Path(sink)
    if not sink.exists():
        raise FileNotFoundError(f"Sink path does not exist: {sink}")
    
    lock_product_path = str(sink) + "_lock.json"
    return Path(lock_product_path)

def get_lock_product(sink:Path|str) -> Optional[LockProduct]:
    '''
    Get the LockProduct for a given sink path by reading the corresponding lock product JSON file.
    '''
    lock_product_path = get_lock_product_path(sink)
    if not lock_product_path.exists():
        return None
    with open(lock_product_path, "r") as f:
        lock_product_data = f.read()

    return LockProduct.model_validate_json(lock_product_data)

def write_lock_product(lock_product:LockProduct) -> Path:
    '''
    Write a LockProduct to a JSON file at the corresponding lock product path.
    '''
    lock_product_path = get_lock_product_path(lock_product.sink)
    lock_product_path.write_text(lock_product.model_dump_json(indent=2), encoding="utf-8")
    return lock_product_path

class DependecyLockFile(BaseModel):
    """Top-level lockfile: a fully-resolved, reproducible product manifest.

    The lockfile is date-scoped — one lockfile per processing day.
    """
    station: str = Field(..., description="Name of the station this lockfile corresponds to, e.g. 'ALIC'.")
    date: str = Field(..., description="Processing date this lockfile corresponds to, in YYYY-MM-DD format.")
    package: str = Field(..., description="Name of the package this lockfile corresponds to, e.g. 'PRIDE'.")
    task: str = Field(..., description="Name of the processing task this lockfile corresponds to, e.g. 'PPP'.")
    version: str = Field("0", description="Version of the lockfile format, for future compatibility.")
    requires_date: bool = Field(True, description="Whether the lockfile is date-scoped (one lockfile per processing day).")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(), description="ISO 8601 timestamp of when the lockfile was created.")
    products: List[LockProduct] = Field(default_factory=list)
    metadata: Optional[dict] = Field(None, description="Optional additional metadata about the lockfile or resolution process.")


def get_dependency_lockfile_name(station:Optional[str],package:str,task:str,date: str| datetime.datetime,version:str="0") -> str:
    '''
    Get the path to the dependency lockfile for a given station, package, task, and date.
    '''
    
    if isinstance(date, str):
        # make sure we have a valid format
        try:
            date = datetime.datetime.strptime(date, "%Y-%m-%d")
        except Exception as e:
            try:
                date = datetime.datetime.fromisoformat(date)  # try ISO format
            except Exception as e:
                raise ValueError(f"Invalid date format: {date}. Expected YYYY-MM-DD or ISO format.") from e

    try:
        YYYY,DOY = date.strftime("%Y"), date.timetuple().tm_yday
    except Exception as e:
        raise ValueError(f"Invalid date value: {date}. Expected datetime or string in YYYY-MM-DD format.") from e

        
    lockfile_name = "_".join([station or "", package, task, str(YYYY),str(DOY).zfill(3), version]) + "_lock.json"

    return lockfile_name

def get_dependency_lockfile(directory:Path, station:Optional[str], package:str, task:str, version:str="0", date:Optional[datetime.datetime | str] = None) -> Tuple[Optional[DependecyLockFile], Optional[Path]]:
    '''
    Get the DependencyLockFile for a given station, package, task, and date by reading the corresponding lockfile JSON file.
    '''
    lockfile_name = get_dependency_lockfile_name(station=station, package=package, task=task, version=version, date=date)
    lockfile_path = directory / lockfile_name
    if not lockfile_path.exists():
        return None, lockfile_path
    
    dep_lockfile_data = lockfile_path.read_text(encoding="utf-8")


    return DependecyLockFile.model_validate_json(dep_lockfile_data), lockfile_path

def write_dependency_lockfile(lockfile:DependecyLockFile, directory:Path,update:bool=False) -> Path:
    '''
    Write a DependencyLockFile to a JSON file in the specified directory with a name based on its station, package, task, and date.
    '''
    lockfile_name = get_dependency_lockfile_name(lockfile.station, lockfile.package, lockfile.task, date=lockfile.date)
    lockfile_path = directory / lockfile_name
    if lockfile_path.exists() and not update:
        raise FileExistsError(f"Lockfile already exists: {lockfile_path}, consider incrementing the version.")
    lockfile_path.write_text(lockfile.model_dump_json(indent=2), encoding="utf-8")
    return lockfile_path