"""
Centralized application configuration.

All environment-dependent values (database location, external API settings,
collector schedule) are read here, once, via pydantic-settings. Nothing
else in the app should call os.environ directly — import `settings` instead.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "sqlite:///./market_pulse.db"

    # poe.ninja data source
    poe_league: str = "Runes of Aldur"
    collector_interval_minutes: int = 10

    # App
    app_env: str = "development"


settings = Settings()
