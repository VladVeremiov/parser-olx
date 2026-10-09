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


def url_exists(url: str) -> bool:
    """Есть ли объявление с таким адресом в базе (чтобы не собирать повторно)."""
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM ads WHERE url = ?", (url,)).fetchone()
    return row is not None


def count_ads() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM ads").fetchone()[0]


def sample_rows(limit: int = 3) -> list[tuple]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, title, author_name, phone FROM ads LIMIT ?", (limit,)
        ).fetchall()


if __name__ == "__main__":
    init_db()
    print("База:", DB_PATH)
    print("Строк в таблице:", count_ads())
    for row in sample_rows():
        print(row)