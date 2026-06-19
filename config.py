import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "recipes.db"


@dataclass(frozen=True)
class Settings:
    bot_token: str
    channel_id: str
    post_time: str
    timezone: str


def load_settings() -> Settings:
    _load_env_file(BASE_DIR / ".env")

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    channel_id = os.getenv("CHANNEL_ID", "@feelflo").strip()
    post_time = os.getenv("POST_TIME", "10:00").strip()
    timezone = os.getenv("TIMEZONE", "Europe/Moscow").strip()

    if not bot_token:
        raise RuntimeError("BOT_TOKEN не найден. Добавьте токен бота в файл .env")

    return Settings(
        bot_token=bot_token,
        channel_id=channel_id,
        post_time=post_time,
        timezone=timezone,
    )


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
