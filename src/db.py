import sqlite3
from pathlib import Path

# Путь к файлу базы: <корень проекта>/data/olx.db
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "olx.db"


def get_connection() -> sqlite3.Connection:
    """Открывает соединение с базой (файл создаётся сам, если его нет)."""
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Создаёт таблицу ads, если её ещё нет."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ads (
                id          INTEGER PRIMARY KEY,
                title       TEXT NOT NULL,
                description TEXT,
                url         TEXT NOT NULL,
                author_name TEXT,
                phone       TEXT
            )
            """
        )


def save_ad(ad_id, title, description, url, author_name, phone) -> None:
    """Записывает объявление. Если такой id уже есть, обновляет строку."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO ads (id, title, description, url, author_name, phone)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title       = excluded.title,
                description = excluded.description,
                url         = excluded.url,
                author_name = excluded.author_name,
                phone       = COALESCE(excluded.phone, ads.phone)
            """,
            (ad_id, title, description, url, author_name, phone),
        )


def ad_exists(ad_id) -> bool:
    """Проверяет, есть ли объявление в базе (нужно, чтобы не собирать повторно)."""
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM ads WHERE id = ?", (ad_id,)).fetchone()
    return row is not None


def count_ads() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]


if __name__ == "__main__":
    init_db()
    print("База готова:", DB_PATH)
    print("Строк в таблице:", count_ads())