import re

import pytest

from src import db

AD_URL = re.compile(r"^https://www\.olx\.ua/d/uk/obyavlenie/[\w\-.]+\.html$")
PHONE = re.compile(r"^\+380\d{9}$")

# По заданию нужно 500 объявлений. Допуск небольшой: часть страниц может не открыться
# (объявление снято, таймаут), такие попадают в список «не удалось собрать».
MIN_ADS = 490


@pytest.fixture(scope="module")
def rows():
    if not db.DB_PATH.exists():
        pytest.skip("Файл базы не найден: сначала запустите main.py")
    with db.get_connection() as conn:
        return conn.execute(
            "SELECT id, title, description, url, author_name, phone FROM ads"
        ).fetchall()


def test_enough_ads_collected(rows):
    assert len(rows) >= MIN_ADS


def test_ids_are_unique(rows):
    ids = [r[0] for r in rows]
    assert len(ids) == len(set(ids))


def test_urls_are_unique(rows):
    urls = [r[3] for r in rows]
    assert len(urls) == len(set(urls))


def test_titles_are_not_empty(rows):
    empty = [r[0] for r in rows if not (r[1] or "").strip()]
    assert not empty, f"Пустой заголовок у объявлений: {empty}"


def test_urls_look_like_olx_ads(rows):
    bad = [r[3] for r in rows if not AD_URL.match(r[3])]
    assert not bad, f"Странные адреса: {bad[:3]}"


def test_phones_have_valid_format(rows):
    bad = [r[0] for r in rows if r[5] is not None and not PHONE.match(r[5])]
    assert not bad, f"Неверный формат телефона у объявлений: {bad}"


def test_at_least_some_phones_collected(rows):
    # Не все продавцы показывают номер, но полностью пустая колонка означала бы сбой.
    assert any(r[5] for r in rows)