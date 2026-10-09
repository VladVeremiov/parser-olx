from playwright.sync_api import sync_playwright

PROFILE_DIR = "data/browser_profile"
SESSION_FILE = "data/olx_session.json"

with sync_playwright() as p:
    # channel="chrome" запускает ваш установленный Google Chrome:
    # Google охотнее пускает на вход через него, чем через встроенный Chromium
    context = p.chromium.launch_persistent_context(
        PROFILE_DIR,
        channel="chrome",
        headless=False,
        no_viewport=True,
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://www.olx.ua/uk/", wait_until="domcontentloaded", timeout=60000)

    input("Войдите в аккаунт OLX в открытом окне. Когда увидите «Ваш профіль» в шапке, нажмите Enter здесь...")

    context.storage_state(path=SESSION_FILE)
    print("Сессия сохранена:", SESSION_FILE)
    context.close()