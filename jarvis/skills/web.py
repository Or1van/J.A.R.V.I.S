"""Інтернет і браузер: сайти, пошук, адресний рядок, вкладки, гортання, назад/вперед."""
import os
import re
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

from jarvis.core import runtime
from jarvis.core.desktop import (
    bring_to_front, find_window_by_process, hotkey, paste_text, press, user_window, window_process,
)
from jarvis.core.registry import CLOSE, OPEN, command, tool
from jarvis.core.text import ORDINAL, parse_ordinal

CHROME_PATHS = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / r"Google\Chrome\Application\chrome.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / r"Google\Chrome\Application\chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / r"Google\Chrome\Application\chrome.exe",
]
BROWSERS = ("chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe")

SITES = {
    "ютуб": "https://www.youtube.com", "youtube": "https://www.youtube.com",
    "гугл": "https://www.google.com", "google": "https://www.google.com",
    "пошту": "https://mail.google.com", "пошта": "https://mail.google.com", "gmail": "https://mail.google.com",
    "вікіпедію": "https://uk.wikipedia.org", "вікіпедія": "https://uk.wikipedia.org",
    "гітхаб": "https://github.com", "github": "https://github.com",
    "перекладач": "https://translate.google.com",
    "карти": "https://maps.google.com", "мапи": "https://maps.google.com",
    "клод": "https://claude.ai", "claude": "https://claude.ai",
    "дак дак го": "https://duckduckgo.com", "duckduckgo": "https://duckduckgo.com",
}
SITE_RE = "|".join(SITES)
SEARCH_URLS = {
    "google": "https://www.google.com/search?q=",
    "youtube": "https://www.youtube.com/results?search_query=",
    "wikipedia": "https://uk.wikipedia.org/w/index.php?search=",
}
YOUTUBE = r"(?:ютубі|ютуб|youtube)"
DOMAIN = re.compile(r"[\w-]+(?:\.[\w-]+)+", re.I)
TAB = r"вкладк\w*"
# Куди "написати" в браузері: "напиши в гуглі ...", "введи в адресний рядок ..."
ADDRESS_BAR = r"(?:гугл\w*|google|пошук\w*|адресн\w* рядок\w*|рядок\w*|браузер\w*|хром\w*|chrome)"


def browse(url: str) -> None:
    """Відкриває адресу в браузері з налаштувань (за замовчуванням — Chrome)."""
    try:
        choice = runtime.settings().browser
    except RuntimeError:
        choice = "chrome"
    exe = None
    if choice == "chrome":
        exe = next((p for p in CHROME_PATHS if p.exists()), None)
    elif choice != "default" and Path(choice).exists():
        exe = Path(choice)
    if exe:
        subprocess.Popen([str(exe), url])
    else:
        webbrowser.open(url)


def focus_browser() -> bool:
    """Переводить фокус у браузер: той, з яким ви працюєте, або будь-який відкритий."""
    win = user_window()
    if win is None or window_process(win._hWnd) not in BROWSERS:
        win = next((w for b in BROWSERS if (w := find_window_by_process(b))), None)
    return win is not None and bring_to_front(win)


@tool
def open_url(url: str) -> str:
    """Відкрити сайт у браузері.

    Args:
        url: Адреса сайту, напр. "https://youtube.com".
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    browse(url)
    return "Відкриваю."


@tool
def open_site_named(name: str) -> str:
    """Відкрити сайт за назвою або адресою, коли точна адреса невідома (напр. "DuckDuckGo", "розетка", "olx.ua").

    Args:
        name: Назва сайту або адреса.
    """
    domain = DOMAIN.search(name)
    if domain:
        return open_url(domain.group())
    # "\запит" у DuckDuckGo одразу переходить на перший результат пошуку
    browse("https://duckduckgo.com/?q=" + quote_plus("\\" + name))
    return f"Відкриваю сайт {name}."


@tool
def search_web(query: str, site: str = "google") -> str:
    """Знайти щось в інтернеті — відкриває результати пошуку в браузері.

    Args:
        query: Пошуковий запит.
        site: Де шукати: "google", "youtube" або "wikipedia".
    """
    browse(SEARCH_URLS.get(site, SEARCH_URLS["google"]) + quote_plus(query))
    return f"Шукаю «{query}»."


@tool
def browser_go(text: str) -> str:
    """Ввести адресу сайту або пошуковий запит в адресний рядок браузера і перейти (у поточній вкладці).

    Args:
        text: Адреса (напр. "duckduckgo.com") або пошуковий запит.
    """
    if not focus_browser():
        return open_url(text) if DOMAIN.fullmatch(text.strip()) else search_web(text)
    press("ctrl", "l")
    time.sleep(0.15)
    paste_text(text)
    press("enter")
    return "Готово."


def _raw_after(pattern: str) -> str:
    """Точний текст команди після службових слів (напр. після "напиши в гуглі")."""
    return re.sub(rf"^.*?{pattern}[\s,:]*", "", runtime.command_text(), count=1, flags=re.I).strip()


def _browser_keys(*keys: str):
    if not focus_browser():
        return "Браузер не відкритий."
    press(*keys)


# ---------- сайти й пошук ----------

@command(rf"{OPEN} (?:сайт )?(?P<site>{SITE_RE})", priority=3)
def _open_site(site):
    return open_url(SITES[site])


@command(rf"{OPEN} сайт (?P<name>.+)", priority=2)
def _open_named_site(name):
    return open_site_named(_raw_after(r"сайт") or name)


@command(rf"{OPEN} браузер", priority=3)
def _open_browser():
    return open_url(SITES["google"])


@command(
    rf"(?:знайди|пошукай|увімкни|включи) (?:на |в )?{YOUTUBE} (?P<query>.+)",
    rf"(?:знайди|пошукай|увімкни|включи) (?P<query>.+?) (?:на|в) {YOUTUBE}",
    priority=3,
)
def _search_youtube(query):
    return search_web(query, "youtube")


@command(r"(?:знайди|пошукай|загугли) (?:в інтернеті |в гуглі |в google )?(?P<query>.+)", priority=1)
def _search_google(query):
    return search_web(query, "google")


@command(rf"(?:напиши|введи|вбий|набери|пошукай) (?:в |у )?{ADDRESS_BAR} (?P<text>.+)", priority=4)
def _address_bar(text):
    return browser_go(_raw_after(ADDRESS_BAR) or text)


@command(r"знайди на сторінці (?P<text>.+)", priority=4)
def _find_on_page(text):
    if not focus_browser():
        return "Браузер не відкритий."
    press("ctrl", "f")
    time.sleep(0.15)
    paste_text(_raw_after(r"сторінці") or text)


# ---------- вкладки ----------

@command(rf"(?:нова|відкрий нову) {TAB}", priority=4)
def _new_tab():
    return _browser_keys("ctrl", "t")


@command(rf"{CLOSE} {TAB}", priority=4)
def _close_tab():
    return _browser_keys("ctrl", "w")


@command(rf"(?:поверни|відкрий) закриту {TAB}", priority=4)
def _reopen_tab():
    return _browser_keys("ctrl", "shift", "t")


@command(rf"наступна {TAB}", priority=4)
def _next_tab():
    return _browser_keys("ctrl", "tab")


@command(rf"попередня {TAB}", priority=4)
def _previous_tab():
    return _browser_keys("ctrl", "shift", "tab")


@command(rf"(?:перейди на|відкрий|перемкнись на|переключись на) (?P<n>{ORDINAL}|останн\w*) {TAB}", priority=4)
def _tab_number(n):
    number = 9 if n.startswith("останн") else parse_ordinal(n)
    if number is None:
        return None
    return _browser_keys("ctrl", str(min(number, 9)))


# ---------- навігація й перегляд (працює і в інших програмах) ----------

@command(r"назад|повернись назад|сторінка назад", priority=4)
def _back():
    hotkey("alt", "left")


@command(r"вперед|сторінка вперед", priority=4)
def _forward():
    hotkey("alt", "right")


@command(r"(?:онови|оновити|перезавантаж)(?: сторінку)?", priority=4)
def _reload():
    hotkey("f5")


@command(r"(?:прокрути|гортай|покрути|скрол\w*)(?: сторінку)?(?: вниз| донизу)?(?: ще)?", priority=4)
def _scroll_down():
    hotkey("pagedown")


@command(r"(?:прокрути|гортай|покрути|скрол\w*)(?: сторінку)? (?:вгору|догори)(?: ще)?", priority=4)
def _scroll_up():
    hotkey("pageup")


@command(r"на початок(?: сторінки)?|(?:прокрути|гортай) на початок", priority=4)
def _top():
    hotkey("home")


@command(r"в кінець(?: сторінки)?|(?:прокрути|гортай) в кінець", priority=4)
def _bottom():
    hotkey("end")


@command(r"(?:збільш|наблиз)\w*(?: масштаб| сторінку| текст)?", priority=4)
def _zoom_in():
    hotkey("ctrl", "=")


@command(r"(?:зменш|віддал)\w*(?: масштаб| сторінку| текст)?", priority=4)
def _zoom_out():
    hotkey("ctrl", "-")


@command(r"(?:звичайний|нормальний) масштаб", priority=4)
def _zoom_reset():
    hotkey("ctrl", "0")


@command(r"на весь екран|повноекранний режим|вийди з повноекранного режиму", priority=4)
def _fullscreen():
    hotkey("f11")
