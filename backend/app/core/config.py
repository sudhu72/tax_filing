from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Tax Filing Multi-Agent App"
    data_dir: str = "data"
    allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    smtp_enabled: bool = False
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_from: str = "noreply@local.tax"
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = False

    webhook_enabled: bool = False
    webhook_timeout_seconds: int = 10

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    @property
    def runs_dir(self) -> Path:
        path = Path(self.data_dir) / "runs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def schemas_dir(self) -> Path:
        path = Path(self.data_dir) / "schemas"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
