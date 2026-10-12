import logging
import re
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from src import config

log = logging.getLogger(__name__)

# Селектори
TITLE = "[data-cy='offer_title']"
DESCRIPTION = "[data-cy='ad_description']"
AUTHOR = "[data-cy='seller_card'] h4"
FOOTER = "[data-cy='ad-footer-bar-section']"
COOKIES_BUTTON = "[data-cy='dismiss-cookies-overlay']"

PHONE_BUTTON_NAME = re.compile(r"Показати телефон", re.I)

PHONE_TEXT = re.compile(r"^\+?[\d ()\-]{9,}$")

BLOCK_MESSAGE = re.compile(r"підозр\w*\s+активн", re.I)


@dataclass
class AdData:
    ad_id: int
    title: str
    description: Optional[str]
    url: str
    author_name: Optional[str]
    phone: Optional[str]
    # ok / no_button / disallowed / blocked / not_found
    phone_status: str


def normalize_phone(raw: str) -> str:
    """Привід номера до виду +380XXXXXXXXX.

    '+38 067 6024805'  -> '+380676024805'
    '634 352 502'      -> '+380634352502'
    '380 050 5542835'  -> '+380505542835'  (код країни плюс зайвий нуль)
    """
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("3800") and len(digits) == 13:
        digits = "380" + digits[4:]
    elif len(digits) == 10 and digits.startswith("0"):
        digits = "38" + digits
    elif len(digits) == 9:
        digits = "380" + digits
    return "+" + digits


class AdPage:
    "Сторінка одного оголошення: знає, де що лежить, і вміє це забрати."

    def __init__(self, page: Page):
        self.page = page
        # Після першого блокування антифродом кнопку телефону більше не натискаємо
        self.phone_blocked = False
        self.not_found_streak = 0

    def open(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded", timeout=config.PAGE_TIMEOUT_MS)
        # чекаємо заголовок: якщо його немає, оголошення знято або не пустило
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
        if lines[0].strip() == "Опис":
            lines = lines[1:]
        return "\n".join(lines).strip() or None

    def get_ad_id(self) -> Optional[int]:
        match = re.search(r"ID:\s*(\d+)", self._text(FOOTER) or "")
        return int(match.group(1)) if match else None

    def _button_texts(self) -> list[str]:
        """Тексти всіх кнопок на сторінці (нерозривні пробіли замінені звичайними)."""
        raw = self.page.get_by_role("button").all_inner_texts()
        return [t.replace("\xa0", " ").strip() for t in raw]

    @staticmethod
    def _find_phone(texts: list[str]) -> Optional[str]:
        """Шукає серед текстів кнопок той, де написано номер"""
        for text in texts:
            digits = re.sub(r"\D", "", text)
            if PHONE_TEXT.match(text) and 9 <= len(digits) <= 13:
                return text
        return None

    def _block_line(self) -> Optional[str]:
        """Повертає рядок із повідомленням антифрода, якщо він є на сторінці."""
        for line in self.page.inner_text("body").split("\n"):
            if BLOCK_MESSAGE.search(line):
                return line.strip()
        return None

    def get_phone(self) -> tuple[Optional[str], str]:
        """Повертає (номер або None, статус)."""
        button = self.page.get_by_role("button", name=PHONE_BUTTON_NAME)
        try:
            button.first.wait_for(timeout=4000)
        except PlaywrightTimeout:
            return None, "no_button"

        if self.phone_blocked:
            return None, "blocked"

        button.first.click()

        # номер може з'явитися не одразу: перевіряємо до трьох разів
        texts: list[str] = []
        for _ in range(3):
            self.page.wait_for_timeout(1500)
            if "Disallowed" in self.page.inner_text("body"):
                return None, "disallowed"
            block = self._block_line()
            if block:
                self.phone_blocked = True
                log.warning("OLX заблокировал показ номеров: %r. "
                            "Дальше кнопку не нажимаю.", block)
                return None, "blocked"
            texts = self._button_texts()
            found = self._find_phone(texts)
            if found:
                self.not_found_streak = 0
                return normalize_phone(found), "ok"

        # номер так и не появился: пишем в лог, что было на кнопках (для разбора)
        log.warning("Номер не найден. Кнопки на странице: %r", texts[:15])
        self.not_found_streak += 1
        if self.not_found_streak >= config.SOFT_BLOCK_STREAK:
            self.phone_blocked = True
            log.warning("Номер не показался %s раза подряд: похоже на тихое "
                        "ограничение OLX. Дальше кнопку не нажимаю.", self.not_found_streak)
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