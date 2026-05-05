import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)


class Settings(BaseSettings):
    app_name: str = "AIRIS Backend"
    app_env: str = "development"
    debug: bool = False

    # Supabase/PostgreSQL SQLAlchemy URL.
    # Example: postgresql+psycopg://postgres:password@host:5432/postgres
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "DATABASE_URL",
            "database_url",
            "DB_URL",
            "SUPABASE_DB_URL",
            "SUPABASE_DATABASE_URL",
        ),
    )
    test_database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("TEST_DATABASE_URL", "test_database_url"),
    )

    # Supabase REST URL (for API clients). This is NOT a SQLAlchemy DB URL.
    supabase_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_URL", "supabase_url"),
    )

    # Optional target schema if you want to scope reflection and migrations.
    db_schema: str | None = None
    jwt_secret_key: str = Field(
        default="change-me-in-production",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "jwt_secret_key"),
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias=AliasChoices("JWT_ALGORITHM", "jwt_algorithm"))
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )

    # Frontend base URL for invite links (no trailing slash required).
    frontend_url: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("FRONTEND_URL", "frontend_url"),
    )

    # Brevo SMTP (https://developers.brevo.com/docs/send-transactional-emails-using-smtp-relay)
    smtp_host: str = Field(
        default="smtp-relay.brevo.com",
        validation_alias=AliasChoices("SMTP_HOST", "smtp_host"),
    )
    smtp_port: int = Field(default=587, validation_alias=AliasChoices("SMTP_PORT", "smtp_port"))
    smtp_user: str | None = Field(default=None, validation_alias=AliasChoices("SMTP_USER", "smtp_user"))
    smtp_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_PASSWORD", "smtp_password"),
    )
    smtp_from: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_FROM", "smtp_from"),
    )

    # Groq API key for AI-powered JD parsing.
    groq_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY", "groq_api_key"),
    )

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_database_config(self) -> "Settings":
        if self.database_url:
            if self.database_url.startswith("postgresql://"):
                # Default "postgresql://" makes SQLAlchemy try psycopg2.
                # This project uses psycopg (v3), so normalize the URL automatically.
                self.database_url = self.database_url.replace(
                    "postgresql://",
                    "postgresql+psycopg://",
                    1,
                )
            return self

        if self.supabase_url:
            raise ValueError(
                "DATABASE_URL is required for backend DB access. "
                "You currently provided SUPABASE_URL/supabase_url (REST URL), which cannot be used by SQLAlchemy/Alembic. "
                "Set DATABASE_URL (or SUPABASE_DB_URL) to your Postgres connection string."
            )

        raise ValueError(
            "DATABASE_URL is required. Set DATABASE_URL (or SUPABASE_DB_URL) in backend/.env."
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    print("DATABASE_URL:", os.getenv("DATABASE_URL"))
    return Settings()


def get_cors_origins(raw_origins: str) -> list[str]:
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

