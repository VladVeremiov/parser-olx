import logging
import random
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from main import setup_logging
from src import config, db
from src.pages.ad_page import AdPage

log = logging.getLogger("retry_phones")

LOG_FILE = Path("logs/scraper.log")
STATUS_LINE = re.compile(r"ID (\d+): телефон (\w+)")
RETRY_STATUSES = {"not_found", "blocked", "disallowed"}


def last_statuses() -> dict[int, str]:
    """Последний статус телефона для каждого ID из лога основного сбора."""
    statuses: dict[int, str] = {}
    for ad_id, status in STATUS_LINE.findall(LOG_FILE.read_text(encoding="utf-8")):
        statuses[int(ad_id)] = status
    return statuses


def candidates() -> list[tuple[int, str]]:
    """Объявления, где кнопка была, номер не получен, и в базе телефон пуст."""
    statuses = last_statuses()
    with db.get_connection() as conn:
        rows = conn.execute("SELECT id, url FROM ads WHERE phone IS NULL").fetchall()
    return [(ad_id, url) for ad_id, url in rows if statuses.get(ad_id) in RETRY_STATUSES]


def main() -> None:
    setup_logging()
    todo = candidates()
    log.info("Кандидатов на добор: %s, лимит нажатий за запуск: %s",
             len(todo), config.PHONE_RETRY_LIMIT)

    clicks = 0
    got = 0
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(config.CDP_URL)
        page = browser.contexts[0].new_page()
        ad_page = AdPage(page)
        try:
            for ad_id, url in todo:
                if clicks >= config.PHONE_RETRY_LIMIT:
                    log.info("Достигнут лимит нажатий за запуск, останавливаюсь")
                    break
                try:
                    ad_page.open(url)
                    phone, status = ad_page.get_phone()
                except Exception as exc:
                    log.warning("ID %s: не открылось, пропускаю: %s", ad_id, exc)
                    continue

                if status != "no_button":
                    clicks += 1  # кнопка была нажата
                if status == "ok":
                    with db.get_connection() as conn:
                        conn.execute("UPDATE ads SET phone = ? WHERE id = ?", (phone, ad_id))
                    got += 1
                    log.info("ID %s: номер добран (%s/%s нажатий)",
                             ad_id, clicks, config.PHONE_RETRY_LIMIT)
                elif status == "blocked":
                    log.warning("OLX снова включил защиту, останавливаюсь. "
                                "Повторите добор позже.")
                    break
                else:
                    log.info("ID %s: статус %s", ad_id, status)
                time.sleep(random.uniform(*config.PHONE_RETRY_DELAY_S))
        finally:
            page.close()

    print("\n=== Итог добора ===")
    print("Кандидатов было:", len(todo))
    print("Нажатий кнопки:", clicks)
    print("Номеров добавлено:", got)
    print("Осталось без номера из кандидатов:", len(todo) - got)


if __name__ == "__main__":
    main()