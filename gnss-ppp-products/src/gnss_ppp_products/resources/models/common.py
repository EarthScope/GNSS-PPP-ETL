"""
Common Pydantic models used across different modules.
"""

from pydantic import BaseModel

class Solution(BaseModel):
    code: str
    prefix: str
    description: str = ""
