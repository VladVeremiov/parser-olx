import logging
import random
import time
from collections import Counter

from playwright.sync_api import Page

from src import config, db
from src.pages.ad_page import AdData, AdPage
from src.pages.listing_page import ListingPage

log = logging.getLogger(__name__)


def pause() -> None:
    """Случайная пауза, чтобы не долбить сайт запросами без перерыва."""
    time.sleep(random.uniform(*config.DELAY_RANGE_S))


def collect_links(page: Page, target: int) -> list[str]:
    """Листает страницы списка, пока не наберёт target уникальных ссылок."""
    listing = ListingPage(page)
    links: dict[str, None] = {}  # словарь вместо списка: нет дублей, порядок сохраняется
    failures = 0

    for number in range(1, config.MAX_PAGES + 1):
        try:
            listing.open(number)
            page_links = listing.get_links()
            failures = 0
        except Exception as exc:
            failures += 1
            log.warning("Страница %s не открылась (%s подряд): %s", number, failures, exc)
            if failures >= 3:
                log.error("Три сбоя подряд, останавливаю сбор ссылок")
                break
            continue

        before = len(links)
        for link in page_links:
            links.setdefault(link, None)
        log.info(
            "Страница %s: на странице %s, новых %s, всего %s",
            number, len(page_links), len(links) - before, len(links),
        )

        if len(links) >= target:
            break
        pause()

    return list(links)[:target]


def scrape_ad(ad_page: AdPage, url: str) -> AdData | None:
    """Собирает одно объявление; при сбое повторяет с растущей паузой."""
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            return ad_page.collect(url)
        except Exception as exc:
            log.warning("Попытка %s/%s не удалась для %s: %s",
                        attempt, config.MAX_RETRIES, url, exc)
            if attempt < config.MAX_RETRIES:
                time.sleep(5 * attempt)
    return None


def run(page: Page, target: int) -> tuple[Counter, list[str]]:
    """Полный цикл: собрать ссылки, обойти объявления, записать в базу."""
    db.init_db()
    links = collect_links(page, target)
    log.info("Ссылок собрано: %s. Начинаю обход объявлений", len(links))

    ad_page = AdPage(page)
    stats: Counter = Counter()
    failed: list[str] = []
    consecutive_failures = 0

    for index, url in enumerate(links, 1):
        if db.url_exists(url):
            stats["skipped"] += 1
            continue

        ad = scrape_ad(ad_page, url)
        if ad is None:
            failed.append(url)
            consecutive_failures += 1
            if consecutive_failures >= config.MAX_CONSECUTIVE_FAILURES:
                log.error("%s сбоев подряд, останавливаюсь. Запустите ещё раз позже: "
                          "собранное сохранено, повторный запуск продолжит с этого места.",
                          consecutive_failures)
                break
            continue

        consecutive_failures = 0
        db.save_ad(ad.ad_id, ad.title, ad.description, ad.url, ad.author_name, ad.phone)
        stats[ad.phone_status] += 1
        log.info("[%s/%s] ID %s записан, телефон: %s", index, len(links), ad.ad_id, ad.phone_status)
        pause()

    return stats, failed