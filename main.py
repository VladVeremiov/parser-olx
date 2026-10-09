import argparse
import logging
from pathlib import Path

from playwright.sync_api import sync_playwright

from src import config, db
from src.scraper import run


def setup_logging() -> None:
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/scraper.log", encoding="utf-8"),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Сбор объявлений OLX в SQLite")
    parser.add_argument("--limit", type=int, default=config.TARGET_ADS,
                        help="сколько объявлений собрать (по умолчанию из config.py)")
    args = parser.parse_args()
    setup_logging()

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(config.CDP_URL)
        page = browser.contexts[0].new_page()
        try:
            stats, failed = run(page, args.limit)
        finally:
            page.close()

    print("\n=== Итог ===")
    print("Строк в базе:", db.count_ads())
    print("Статусы телефонов:", dict(stats))
    print("Не удалось собрать:", len(failed))
    for url in failed:
        print("  ", url)


if __name__ == "__main__":
    main()