from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
import datetime
from typing import List, Optional, Union

class BaseConfig(BaseModel):
    """Base configuration model with common settings."""
    date: Optional[datetime.datetime | datetime.date] = None
    
    model_config = ConfigDict(
        #use_enum_values=True,  # Serialize enums using their values
    )
    @field_serializer("date")
    def _serialize_date(self, date: Optional[datetime.datetime | datetime.date]) -> Optional[str]:
        if date is None:
            return None
        return date.astimezone(datetime.timezone.utc).isoformat()
    
    @field_validator("date")
    def _validate_date(cls, date: Optional[datetime.datetime | datetime.date]) -> Optional[datetime.datetime | datetime.date]:
        if date is None:
            return None
        if isinstance(date, str):
            return datetime.datetime.fromisoformat(date).astimezone(datetime.timezone.utc)
        return date