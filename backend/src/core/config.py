from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        case_sensitive=False,
        extra='ignore',
    )

    # DEBUG
    debug: bool = False

    # LOGGING (DEBUG | INFO | WARNING | ERROR)
    log_level: str = 'INFO'

    # BACKEND
    backend_url: str = 'http://localhost:8080'
    service_api_key: str

    # DB
    database_url: str
    secret_key: str

    # AUTH
    access_token_expire_minutes: int = 30  # min
    verification_token_ttl_hours: int = 24
    resend_verification_cooldown_seconds: int = 60

    # GOOGLE AUTH
    google_client_id: str
    google_client_secret: str

    # LINKEDIN AUTH
    linkedin_client_id: str
    linkedin_client_secret: str

    # EMAIL
    smtp_host: str = 'smtp-relay.brevo.com'
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    smtp_from_email: str = 'no-reply@azens.net'
    frontend_url: str = 'https://www.azens.net'

    # AWS S3
    aws_access_key: str
    aws_secret_access_key: str
    aws_region: str
    aws_s3_bucket_name: str

    # STRIPE
    stripe_api_key: str
    stripe_webhook_secret: str

    stripe_price_analyst_monthly: str
    stripe_price_analyst_yearly: str

    stripe_price_associate_monthly: str
    stripe_price_associate_yearly: str

    stripe_price_managing_director_monthly: str
    stripe_price_managing_director_yearly: str

    # OPENAI
    openai_api_key: str
    openai_model_feedback: str
    openai_model_interviews: str

    # DAILY
    daily_api_key: str
    daily_room_url: str

    # CARTESIA (STT/TTS)
    cartesia_api_key: str
    cartesia_voice_id_en: str
    cartesia_voice_id_de: str
    cartesia_voice_id_es: str
    cartesia_voice_id_it: str
    cartesia_voice_id_nl: str

    # DEEPGRAM (STT/TTS)
    deepgram_api_key: str

    # PIPECAT
    pipecat_api_key: str
    pipecat_agent_name_cv: str
    pipecat_agent_name_knowledge: str
    pipecat_agent_name_case_study: str


settings = Settings()
