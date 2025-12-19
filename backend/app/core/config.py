from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SpatialAddressPro"
    API_V1_STR: str = "/api/v1"
    
    # Use SQLite for local development without Docker
    # format: sqlite:///./sql_app.db
    DATABASE_URL: str = "sqlite:///./local_dev_v4.db" 

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "ignore"

settings = Settings()
