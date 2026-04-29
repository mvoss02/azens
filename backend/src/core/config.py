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

    zombie_grace_seconds: int = 60

    # SESSION LIMITS (per calendar month, per subscription tier)
    # None = unlimited. The mapping from SubscriptionPlan enum to these
    # values lives in api/sessions.py::_monthly_session_limit — keep the
    # tiers and the values in lockstep when adjusting pricing or plans.
    session_limit_analyst: int = 6
    session_limit_associate: int = 15
    session_limit_managing_director: int | None = None

    # FEEDBACK
    # If the user ends a session after less than this fraction of the scheduled
    # duration (e.g. 0.10 → 3 min into a 30 min interview), skip GPT-4o feedback
    # generation — there's not enough transcript for it to be useful, and the
    # OpenAI call would be wasted. Raise this if you start seeing low-signal
    # reports; lower it if users complain about "no feedback" on short tests.
    feedback_min_session_fraction: float = 0.10

    # DB
    database_url: str
    secret_key: str

    # AUTH
    # Long enough that a single interview (max 90 min superday) can complete
    # without the token aging out mid-session. With no refresh-token flow yet
    # (see tech debt), this is the only knob — too short and users get
    # punted to /login during a long interview, too long and a leaked token
    # stays valid longer. 120 covers the worst case with a comfortable
    # margin; revisit when refresh tokens land.
    access_token_expire_minutes: int = 120  # min
    verification_token_ttl_hours: int = 24
    resend_verification_cooldown_seconds: int = 60
    password_reset_token_ttl_hours: int = 1

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
    stripe_price_analyst_halfyearly: str

    stripe_price_associate_monthly: str
    stripe_price_associate_halfyearly: str

    stripe_price_managing_director_monthly: str
    stripe_price_managing_director_halfyearly: str

    # OPENAI
    openai_api_key: str
    openai_model_feedback: str
    openai_model_interviews: str

    # DAILY
    daily_api_key: str
    daily_room_url: str
    daily_room_grace_seconds: int = 600

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
