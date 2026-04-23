from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(
        env_file=".env",
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
    return Settings()


def get_cors_origins(raw_origins: str) -> list[str]:
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

