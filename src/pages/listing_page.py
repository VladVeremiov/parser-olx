import logging

from playwright.sync_api import Page

from src import config

log = logging.getLogger(__name__)

CARD = "[data-cy='l-card']"
CARD_LINK = "[data-cy='l-card'] a"
COOKIES_BUTTON = "[data-cy='dismiss-cookies-overlay']"
AD_PATH = "/d/uk/obyavlenie/"


class ListingPage:
    """Страница списка объявлений категории: умеет открыть N-ю страницу и отдать ссылки."""

    def __init__(self, page: Page):
        self.page = page

    @staticmethod
    def url_for(page_number: int) -> str:
        if page_number == 1:
            return config.CATEGORY_URL
        return f"{config.CATEGORY_URL}?page={page_number}"

    def open(self, page_number: int) -> None:
        """Открывает страницу списка с номером page_number."""
        self.page.goto(
            self.url_for(page_number),
            wait_until="domcontentloaded",
            timeout=config.PAGE_TIMEOUT_MS,
        )
        self.page.wait_for_selector(CARD, timeout=20_000)
        self.page.wait_for_timeout(1500)
        cookies = self.page.locator(COOKIES_BUTTON)
        if cookies.count():
            cookies.first.click()
        self.load_all_cards()

    def load_all_cards(self) -> None:
        """Прокручивает страницу вниз, чтобы подгрузились все карточки (lazy loading)."""
        stable_rounds = 0
        previous = -1
        for _ in range(25):
            self.page.evaluate("window.scrollBy(0, 1200)")
            self.page.wait_for_timeout(600)
            count = self.page.locator(CARD).count()
            stable_rounds = stable_rounds + 1 if count == previous else 0
            previous = count
            if stable_rounds >= 3:  # число карточек не растёт: всё загрузилось
                break
        log.info("Карточек на странице после прокрутки: %s", previous)

    def get_links(self) -> list[str]:
        """Уникальные ссылки на объявления без хвоста ?search_reason=..., порядок сохраняется."""
        hrefs = self.page.locator(CARD_LINK).evaluate_all("els => els.map(e => e.href)")
        links = [h.split("?")[0] for h in hrefs if AD_PATH in h]
        return list(dict.fromkeys(links))