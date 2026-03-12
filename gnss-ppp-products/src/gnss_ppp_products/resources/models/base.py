from pydantic import BaseModel, ConfigDict

class BaseConfig(BaseModel):
    """Base configuration model with common settings."""
    
    model_config = ConfigDict(
        #use_enum_values=True,  # Serialize enums using their values
    )