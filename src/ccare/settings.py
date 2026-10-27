from pydantic_settings import BaseSettings, SettingsConfigDict

TENANT = "acme"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://ccare:ccare@localhost:5433/ccare"
    ccare_demo_auth: bool = False
    ccare_live: bool = False


def get_settings() -> Settings:
    return Settings()
