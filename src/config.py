CDP_URL = "http://localhost:9222"
PAGE_TIMEOUT_MS = 60_000

CATEGORY_URL = "https://www.olx.ua/uk/detskiy-mir/detskaya-odezhda/"
TARGET_ADS = 500              # скільки унікальних оголошень потрібно зібрати
MAX_PAGES = 25                # запобіжник: далі цієї сторінки не йдемо
DELAY_RANGE_S = (2.0, 4.0)    # випадкова пауза між сторінками, секунди
MAX_RETRIES = 3                # скільки разів пробуємо одне оголошення
MAX_CONSECUTIVE_FAILURES = 5   # стільки збоїв поспіль, і збір зупиняється
PHONE_RETRY_LIMIT = 10               # максимум натискань "Показати телефон" за один запуск добору
SOFT_BLOCK_STREAK = 2                # стільки «номер не здався» поспіль вважаємо обмеженням
PHONE_RETRY_DELAY_S = (8.0, 15.0)    # пауза між оголошеннями при доборі, секунди