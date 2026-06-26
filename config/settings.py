from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Groq
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # MongoDB
    MONGO_URI: str
    MONGO_DB_NAME: str = "resumedata"

    # PostgreSQL
    POSTGRES_DSN: str

    # JWT — must match Java service secret exactly
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"

    # Indeed MCP (specifically for hitting claude job search endpoint)
    # we need to get our own url from https://ads.indeed.com/jobroll/xmlfeed . this is official job search API and we need to signup first
    INDEED_MCP_URL: str = ""

    # App
    APP_PORT: int = 8000
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

# single instance imported everywhere
settings = Settings()