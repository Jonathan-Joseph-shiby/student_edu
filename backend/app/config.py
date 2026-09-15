from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_path: Path
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    anthropic_api_key: str | None
    anthropic_model: str


def get_settings() -> Settings:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY must be set before starting the backend")
    database_path = Path(os.getenv("INDUSTRYPULSE_DB_PATH", str(ROOT / "db" / "industrypulse.sqlite3")))
    return Settings(
        database_path=database_path if database_path.is_absolute() else ROOT / database_path,
        jwt_secret_key=secret,
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
    )