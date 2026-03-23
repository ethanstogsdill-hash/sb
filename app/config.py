from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    site_username: str = ""
    site_password: str = ""
    site_url: str = "https://www.allagentreports.com"

    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/api/gmail/callback"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    bet_check_interval: int = 5  # minutes between scrape checks

    db_path: str = str(Path(__file__).parent.parent / "data" / "sportsbook.db")
    credentials_dir: str = str(Path(__file__).parent.parent / "credentials")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
