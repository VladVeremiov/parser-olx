CDP_URL = "http://localhost:9222"   # адрес Chrome, в котором вы вошли в OLX
PAGE_TIMEOUT_MS = 60_000

CATEGORY_URL = "https://www.olx.ua/uk/detskiy-mir/detskaya-odezhda/"
TARGET_ADS = 500              # сколько уникальных объявлений нужно собрать
MAX_PAGES = 25                # предохранитель: дальше этой страницы не идём
DELAY_RANGE_S = (2.0, 4.0)    # случайная пауза между страницами, секунды