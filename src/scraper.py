import logging
import random
import time

from playwright.sync_api import Page

from src import config
from src.pages.listing_page import ListingPage

log = logging.getLogger(__name__)


def pause() -> None:
    """Случайная пауза, чтобы не долбить сайт запросами без перерыва."""
    time.sleep(random.uniform(*config.DELAY_RANGE_S))


def collect_links(page: Page) -> list[str]:
    """Листает страницы списка, пока не наберёт TARGET_ADS уникальных ссылок."""
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

        if len(links) >= config.TARGET_ADS:
            break
        pause()

    return list(links)[: config.TARGET_ADS]