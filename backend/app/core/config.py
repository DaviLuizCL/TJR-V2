from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://tjr:tjr@db:5432/tjr"
    test_database_url: str = "postgresql+asyncpg://tjr:tjr@db:5432/tjr_test"

    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7

    seed_coordenador_email: str = "admin@tjr.app"
    seed_coordenador_senha: str = "trocar-em-producao"

    timezone: str = "America/Fortaleza"

    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
