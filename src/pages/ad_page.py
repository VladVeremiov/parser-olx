import logging
import re
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from src import config

log = logging.getLogger(__name__)

# Все селекторы в одном месте: если OLX поменяет вёрстку, править только здесь
TITLE = "[data-cy='offer_title']"
DESCRIPTION = "[data-cy='ad_description']"
AUTHOR = "[data-cy='seller_card'] h4"
FOOTER = "[data-cy='ad-footer-bar-section']"
COOKIES_BUTTON = "[data-cy='dismiss-cookies-overlay']"

PHONE_BUTTON_NAME = re.compile(r"Показати телефон", re.I)
# Текст кнопки с номером: только цифры, пробелы, скобки, дефисы (без переводов строки)
PHONE_TEXT = re.compile(r"^\+?[\d ()\-]{9,}$")
# Сообщение антифрода OLX: «...виявили підозрілу активність»
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
    """Приводит номер к виду +380XXXXXXXXX.

    '+38 067 6024805'  -> '+380676024805'
    '634 352 502'      -> '+380634352502'
    '380 050 5542835'  -> '+380505542835'  (код страны плюс лишний ноль)
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
    """Страница одного объявления: знает, где что лежит, и умеет это забрать."""

    def __init__(self, page: Page):
        self.page = page
        # После первой блокировки антифродом кнопку телефона больше не нажимаем
        self.phone_blocked = False

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

    def _button_texts(self) -> list[str]:
        """Тексты всех кнопок на странице (неразрывные пробелы заменены обычными)."""
        raw = self.page.get_by_role("button").all_inner_texts()
        return [t.replace("\xa0", " ").strip() for t in raw]

    @staticmethod
    def _find_phone(texts: list[str]) -> Optional[str]:
        """Ищет среди текстов кнопок тот, где написан номер."""
        for text in texts:
            digits = re.sub(r"\D", "", text)
            if PHONE_TEXT.match(text) and 9 <= len(digits) <= 13:
                return text
        return None

    def _block_line(self) -> Optional[str]:
        """Возвращает строку с сообщением антифрода, если она есть на странице."""
        for line in self.page.inner_text("body").split("\n"):
            if BLOCK_MESSAGE.search(line):
                return line.strip()
        return None

    def get_phone(self) -> tuple[Optional[str], str]:
        """Возвращает (номер или None, статус)."""
        button = self.page.get_by_role("button", name=PHONE_BUTTON_NAME)
        try:
            button.first.wait_for(timeout=4000)  # даём кнопке время появиться
        except PlaywrightTimeout:
            return None, "no_button"

        if self.phone_blocked:
            return None, "blocked"  # антифрод уже сработал: не нажимаем, не провоцируем

        button.first.click()

        # номер может появиться не сразу: проверяем до трёх раз
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
                return normalize_phone(found), "ok"

        # номер так и не появился: пишем в лог, что было на кнопках (для разбора)
        log.warning("Номер не найден. Кнопки на странице: %r", texts[:15])
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