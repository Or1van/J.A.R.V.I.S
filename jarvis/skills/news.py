"""Новини: заголовки з Google Новин українською, технології — з AIN.ua (безкоштовні RSS-стрічки, без ключів).

"Новини" -> Джарвіс питає, які саме, і зачитує 5 заголовків. "Ще" — наступні 5.
"Відкрий третю новину" — відкриває статтю в браузері.
"""
import re
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

from jarvis.core import runtime
from jarvis.core.registry import OPEN, command, tool
from jarvis.core.text import ORDINAL, normalize, parse_ordinal
from jarvis.net import is_online

FEED = "https://news.google.com/rss"
LOCALE = "hl=uk&gl=UA&ceid=UA:uk"
PAGE = 5
# Тема -> (як звучить, розділ Google Новин)
TOPICS = {
    "головні": (r"головн\w*|основн\w*|важлив\w*|усі|всі|останні", None),
    "Україна": (r"україн\w*|в країні", "NATION"),
    "світ": (r"світ\w*|міжнародн\w*|закордон\w*", "WORLD"),
    "економіка": (r"економ\w*|бізнес\w*|фінанс\w*|гроші", "BUSINESS"),
    # Розділ "технології" Google для України видає переважно новини про війну, тому — українське IT-видання
    "технології": (r"технолог\w*|техн\w*|it|айті|гаджет\w*", "https://ain.ua/feed/"),
    "наука": (r"наук\w*|космос\w*", "SCIENCE"),
    "спорт": (r"спорт\w*|футбол\w*", "SPORTS"),
    "здоров'я": (r"здоров\w*|медицин\w*", "HEALTH"),
    "розваги": (r"розваг\w*|кіно|шоу|культур\w*", "ENTERTAINMENT"),
}
TOPIC_RE = "|".join(pattern for pattern, _ in TOPICS.values())
NEWS = r"(?:новини|новин|новинки)"
ORDINAL_SPOKEN = ("Перша", "Друга", "Третя", "Четверта", "П'ята")

_items: list[tuple[str, str, str]] = []  # (заголовок, джерело, посилання) останнього списку
_position = 0


def _topic_of(text: str) -> str | None:
    text = normalize(text)
    for topic, (pattern, _) in TOPICS.items():
        if re.search(rf"\b(?:{pattern})\b", text):
            return topic
    return None


def fetch(topic: str | None = None, query: str | None = None) -> list[tuple[str, str, str]]:
    section = TOPICS[topic][1] if topic else None
    if query:
        url = f"{FEED}/search?q={quote_plus(query)}&{LOCALE}"
    elif section and section.startswith("http"):
        url = section  # окреме видання замість розділу Google Новин
    elif section:
        url = f"{FEED}/headlines/section/topic/{section}?{LOCALE}"
    else:
        url = f"{FEED}?{LOCALE}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    root = ET.fromstring(urllib.request.urlopen(request, timeout=10).read())
    items = []
    for item in root.findall("./channel/item"):
        title = item.findtext("title", "")
        source = item.findtext("source", "")
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        items.append((title.strip(), source, item.findtext("link", "")))
    return items


def _read_page() -> str:
    global _position
    page = _items[_position:_position + PAGE]
    if not page:
        runtime.more = None
        return "Більше новин немає."
    start = _position
    _position += PAGE
    runtime.more = _read_page
    lines = [f"{ORDINAL_SPOKEN[i] if i < len(ORDINAL_SPOKEN) else start + i + 1}: {title}."
             for i, (title, _, _) in enumerate(page)]
    return " ".join(lines) + " Скажіть «ще» або «відкрий другу новину»."


@tool
def read_news(topic: str = "", query: str = "") -> str:
    """Свіжі новини українською: заголовки за темою або про щось конкретне.

    Args:
        topic: Тема: "головні", "Україна", "світ", "економіка", "технології", "наука", "спорт", "здоров'я", "розваги".
        query: Про що новини (напр. "SpaceX"). Якщо задано, тема не потрібна.
    """
    global _items, _position
    if not is_online():
        return "Без інтернету новин не дістану."
    try:
        _items = fetch(_topic_of(topic) if topic else None, query or None)
    except (OSError, ET.ParseError):
        return "Не вдалося завантажити новини."
    _position = 0
    return _read_page()


@command(rf"{NEWS}|що нового|які новини|розкажи {NEWS}|що (?:там )?в світі", priority=6)
def _news():
    choices = ", ".join(list(TOPICS)[:-2])
    runtime.say(f"Які новини: {choices}? Або скажіть, про що.")
    answer = runtime.listen(10)
    if not answer:
        return "Не почув. Скажіть, наприклад, «новини технологій»."
    topic = _topic_of(answer)
    if topic:
        return read_news(topic)
    return read_news(query=re.sub(r"^(?:про|щодо)\s+", "", answer.strip(), flags=re.I))


@command(rf"(?:розкажи |які |що )?{NEWS} (?:в |у |з |із )?(?P<topic>{TOPIC_RE})", priority=7)
def _news_topic(topic):
    return read_news(topic)


@command(rf"(?:розкажи |які |що )?{NEWS} (?:про|щодо) (?P<query>.+)", r"що (?:нового|пишуть) (?:про|щодо) (?P<query>.+)",
         priority=7)
def _news_about(query):
    return read_news(query=query)


@command(rf"{OPEN} (?P<n>{ORDINAL}) новину", rf"(?:детальніше|більше) про (?P<n>{ORDINAL}) новину", priority=7)
def _open_news(n):
    from jarvis.skills.web import browse

    number = parse_ordinal(n)
    if not _items or number is None or not 1 <= number <= len(_items):
        return "Немає такої новини. Спершу скажіть «новини»."
    index = max(0, _position - PAGE) + number - 1  # номер у межах щойно прочитаної п'ятірки
    browse(_items[min(index, len(_items) - 1)][2])
    return "Відкриваю."
