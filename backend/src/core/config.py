from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        case_sensitive=False,
        extra='ignore',
    )
    
    # DEBUG
    debug: bool = False

    # DB
    database_url: str
    secret_key: str

settings = Settings()
