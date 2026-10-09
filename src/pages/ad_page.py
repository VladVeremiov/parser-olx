import logging
import re
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page

from src import config

log = logging.getLogger(__name__)

# Все селекторы в одном месте: если OLX поменяет вёрстку, править только здесь
TITLE = "[data-cy='offer_title']"
DESCRIPTION = "[data-cy='ad_description']"
AUTHOR = "[data-cy='seller_card'] h4"
FOOTER = "[data-cy='ad-footer-bar-section']"
COOKIES_BUTTON = "[data-cy='dismiss-cookies-overlay']"

PHONE_BUTTON_NAME = re.compile(r"Показати телефон", re.I)
PHONE_PATTERN = re.compile(r"(?:\+?38)?[\s\-]?\(?0\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")


@dataclass
class AdData:
    ad_id: int
    title: str
    description: Optional[str]
    url: str
    author_name: Optional[str]
    phone: Optional[str]
    phone_status: str  # ok / no_button / disallowed / not_found


def normalize_phone(raw: str) -> str:
    """'+38 067 6024805' -> '+380676024805'."""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0"):
        digits = "38" + digits
    return "+" + digits


class AdPage:
    """Страница одного объявления: знает, где что лежит, и умеет это забрать."""

    def __init__(self, page: Page):
        self.page = page

    def open(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded", timeout=config.PAGE_TIMEOUT_MS)
        # ждём заголовок: если его нет, объявление снято или нас не пустили
        self.page.wait_for_selector(TITLE, timeout=20_000)
        self.page.wait_for_timeout(1500)
        cookies = self.page.locator(COOKIES_BUTTON)
        if cookies.count():
            cookies.first.click()

    def _text(self, selector: str) -> Optional[str]:
        locator = self.page.locator(selector)
        if not locator.count():
            return None
        return locator.first.inner_text().strip()

    def get_title(self) -> Optional[str]:
        return self._text(TITLE)

    def get_author(self) -> Optional[str]:
        return self._text(AUTHOR)

    def get_description(self) -> Optional[str]:
        text = self._text(DESCRIPTION)
        if not text:
            return None
        lines = text.split("\n")
        if lines[0].strip() == "Опис":  # убираем служебный заголовок блока
            lines = lines[1:]
        return "\n".join(lines).strip() or None

    def get_ad_id(self) -> Optional[int]:
        match = re.search(r"ID:\s*(\d+)", self._text(FOOTER) or "")
        return int(match.group(1)) if match else None

    def get_phone(self) -> tuple[Optional[str], str]:
        """Возвращает (номер или None, статус)."""
        button = self.page.get_by_role("button", name=PHONE_BUTTON_NAME)
        if not button.count():
            return None, "no_button"

        before = set(PHONE_PATTERN.findall(self.page.inner_text("body")))
        button.first.click()
        self.page.wait_for_timeout(2500)

        body = self.page.inner_text("body")
        if "Disallowed" in body:
            return None, "disallowed"

        # берём только те номера, которых до клика на странице не было
        new_numbers = [n for n in PHONE_PATTERN.findall(body) if n not in before]
        if new_numbers:
            return normalize_phone(new_numbers[0]), "ok"
        return None, "not_found"

    def collect(self, url: str) -> AdData:
        self.open(url)
        phone, status = self.get_phone()
        ad_id = self.get_ad_id()
        title = self.get_title()
        if ad_id is None or not title:
            raise ValueError(f"Не удалось прочитать ID или заголовок: {url}")
        log.info("ID %s: телефон %s", ad_id, status)
        return AdData(
            ad_id=ad_id,
            title=title,
            description=self.get_description(),
            url=url,
            author_name=self.get_author(),
            phone=phone,
            phone_status=status,
        )