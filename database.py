import sqlite3
from datetime import datetime

from config import DATA_DIR, DB_PATH


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS published_recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source_url TEXT NOT NULL UNIQUE,
                published_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


def is_recipe_published(source_url: str) -> bool:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM published_recipes WHERE source_url = ? LIMIT 1",
            (source_url,),
        ).fetchone()
    return row is not None


def save_published_recipe(title: str, source_url: str) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO published_recipes (title, source_url, published_at)
            VALUES (?, ?, ?)
            """,
            (title, source_url, datetime.now().isoformat(timespec="seconds")),
        )
        connection.commit()
