from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "VoiceLink Superadmin API"
    ENV: str = "development"
    DEBUG: bool = True

    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "voicelink"

    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8080,http://localhost:8765,http://127.0.0.1:8765"

    # SMTP for outbound mail (currently just password-reset links). Left
    # blank by default — app.core.email logs the message instead of sending
    # it when SMTP_HOST is empty, so forgot-password works out of the box
    # in local dev without real mail credentials configured.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = "no-reply@voicelink.app"
    SMTP_FROM_NAME: str = "VoiceLink Admin"

    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    # Where the emailed reset link points — the frontend's reset-password
    # screen, which reads the `token` query param. Override for whatever
    # host actually serves the frontend outside local dev.
    FRONTEND_RESET_PASSWORD_URL: str = "http://localhost:8765/superadmin/reset-password"

    # Fernet key used to encrypt secrets stored at rest (currently just the
    # superadmin-configurable SMTP password — see app/core/encryption.py).
    # This default is a valid, working key so local dev works out of the
    # box, but it's dev-only: override it in every real deployment, since
    # anyone with the default could decrypt any stored secret.
    ENCRYPTION_KEY: str = "TGtaX9bkRDlrfIB6GRp4rSlaM6N8j53x1upqQmOfhoo="

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
