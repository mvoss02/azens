from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        case_sensitive=False,
        extra='ignore',
    )

    # DEBUG
    debug: bool = False

    # DB
    database_url: str
    secret_key: str

    # AUTH
    access_token_expire_minutes: int = 30  # min
    
    # GOOGLE AUTH
    google_client_id: str
    google_client_secret: str

    # LINKEDIN AUTH
    linkedin_client_id: str
    linkedin_client_secret: str


settings = Settings()
