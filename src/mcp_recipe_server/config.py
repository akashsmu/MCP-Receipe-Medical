import os
import sys
from typing import Optional
from dotenv import load_dotenv

# Load .env from the project root
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)


class Settings:
    """Simple configuration management."""
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")
    

    # LogMeal Configuration
    LOGMEAL_API_KEY: str = os.getenv("LOGMEAL_API_KEY", "")
    LOGMEAL_API_URL: str = os.getenv("LOGMEAL_API_URL", "https://api.logmeal.com/v2")


    # Server Configuration
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
    
    @classmethod
    def validate(cls):
        """Validate required settings."""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        if not cls.OPENAI_API_KEY.startswith("sk-"):
            raise ValueError("OPENAI_API_KEY appears to be invalid")

        if not cls.LOGMEAL_API_KEY:
            raise ValueError("LOGMEAL_API_KEY environment variable is required")

settings = Settings()