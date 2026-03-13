"""
Server connectivity models.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel

class ServerProtocol(str, Enum):
    FTP = "ftp"
    FTPS = "ftps"  # FTP over TLS (e.g., CDDIS)
    HTTP = "http"
    HTTPS = "https"

class Server(BaseModel):
    id: str
    name: str
    protocol: ServerProtocol
    hostname: str
    auth_required: bool = False
    notes: Optional[str] = None
