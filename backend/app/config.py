from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Cibics Tracking API'
    api_v1_prefix: str = '/api/v1'
    secret_key: str = 'change-me-in-env'
    access_token_expire_minutes: int = 60 * 12
    allowed_origins: List[str] = Field(
        default_factory=lambda: ['http://localhost:3100', 'http://127.0.0.1:3100']
    )
    api_port: int = 8200

    db_host: str = 'localhost'
    db_port: int = 5432
    db_name: str = 'cibics'
    db_user: str = 'postgres'
    db_password: str = '123456'

    smtp_host: str = ''
    smtp_port: int = 587
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_use_tls: bool = True
    smtp_from_email: str = 'noreply@cibics.local'
    email_alert_recipients: List[str] = Field(default_factory=list)

    default_super_admin_name: str = 'Super Admin'
    default_super_admin_email: str = 'admin@cibics.local'
    default_super_admin_password: str = 'Admin@123'
    default_assignee_password: str = 'Assignee@123'

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
