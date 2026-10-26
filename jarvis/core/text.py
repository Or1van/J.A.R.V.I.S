"""Робота з текстом команд: нормалізація, слово-активатор, числа, транслітерація."""
import re
from difflib import SequenceMatcher

_APOSTROPHES = str.maketrans({"’": "'", "ʼ": "'", "`": "'", "´": "'"})
# Слова, які не змінюють суть команди: "відкрий мені, будь ласка, браузер" = "відкрий браузер".
_FILLERS = re.compile(r"\b(?:будь ласка|будь-ласка|пожалуйста|мені|нам|ну|будь)\b")

GREETINGS = {"привіт", "ей", "гей", "ок", "окей", "слухай", "hey", "ok", "а", "ну"}
YES_WORDS = {"так", "да", "підтверджую", "звісно", "звичайно", "авжеж", "ага", "yes", "виконуй", "дозволяю", "давай",
             "відправляй", "добре", "гаразд", "окей", "ок", "ok", "згоден", "згодна", "можна", "створюй", "видаляй",
             "відкривай", "роби", "вперед"}
NO_WORDS = {"ні", "нє", "ніт", "нет", "не", "no", "скасуй", "скасувати", "відміна", "відміни", "стоп", "зупинись"}


def normalize(text: str) -> str:
    """Нижній регістр, без розділових знаків і слів-паразитів."""
    t = text.lower().translate(_APOSTROPHES)
    t = re.sub(r"[^\w\s'-]", " ", t)
    t = _FILLERS.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip(" -'")


def split_wake_word(raw: str, wake_words: list[str]) -> tuple[bool, str]:
    """Шукає слово-активатор. Повертає (чи було воно, команда без звертання).
    Звертання на початку ("Джарвіс, ...", "Привіт, Джарвіс, ...") відрізається;
    якщо ім'я всередині команди ("закрий Джарвіса") — текст лишається як є."""
    lower = raw.lower().translate(_APOSTROPHES)
    best = None
    for word in wake_words:
        m = re.search(rf"(?<!\w){re.escape(word)}(?!\w)", lower)
        if m and (best is None or m.start() < best.start()):
            best = m
    if best is None:
        return False, raw
    before = re.sub(r"[^\w\s']", " ", lower[:best.start()]).split()
    if any(w not in GREETINGS for w in before):
        return True, raw
    return True, raw[best.end():].lstrip(" ,.!?:;-—")


def is_yes(text: str | None) -> bool:
    """Згода: перше слово — "так"/"добре"/..., і ніде немає "ні"/"не" ("так або ні" — не згода)."""
    words = normalize(text or "").split()
    return bool(words) and words[0] in YES_WORDS and not any(w in NO_WORDS for w in words)


def is_no(text: str | None) -> bool:
    words = normalize(text or "").split()
    return bool(words) and words[0] in NO_WORDS


_NUMBERS = {
    "нуль": 0, "один": 1, "одна": 1, "два": 2, "дві": 2, "три": 3, "чотири": 4, "п'ять": 5,
    "шість": 6, "сім": 7, "вісім": 8, "дев'ять": 9, "десять": 10, "одинадцять": 11,
    "дванадцять": 12, "тринадцять": 13, "чотирнадцять": 14, "п'ятнадцять": 15,
    "шістнадцять": 16, "сімнадцять": 17, "вісімнадцять": 18, "дев'ятнадцять": 19,
    "двадцять": 20, "тридцять": 30, "сорок": 40, "п'ятдесят": 50, "шістдесят": 60,
    "сімдесят": 70, "вісімдесят": 80, "дев'яносто": 90, "сто": 100,
}


def parse_number(text: str) -> int | None:
    """'тридцять п'ять' -> 35, '40' -> 40. Повертає None, якщо це не число."""
    text = text.strip()
    if text.isdigit():
        return int(text)
    words = text.split()
    if not words or any(w not in _NUMBERS for w in words):
        return None
    return sum(_NUMBERS[w] for w in words)


_ORDINALS = {
    "перш": 1, "друг": 2, "трет": 3, "четверт": 4, "п'ят": 5,
    "шост": 6, "сьом": 7, "восьм": 8, "дев'ят": 9, "десят": 10,
}
ORDINAL = r"(?:перш\w*|друг\w*|трет\w*|четверт\w*|п'ят\w*|шост\w*|сьом\w*|восьм\w*|дев'ят\w*|десят\w*|\d+(?:-?\w+)?)"


def parse_ordinal(text: str) -> int | None:
    """'третій' -> 3, '2-й' -> 2."""
    text = text.strip()
    digits = re.match(r"\d+", text)
    if digits:
        return int(digits.group())
    for stem, value in _ORDINALS.items():
        if text.startswith(stem):
            return value
    return None


def name_stem(name: str) -> str:
    """Прибирає відмінкові закінчення імен для пошуку: 'Максима', 'Максимом' -> 'Максим'.
    Пошук у месенджерах шукає за початком слова, тож основи досить."""
    words = []
    for word in name.split():
        lower = word.lower()
        for ending in ("ові", "еві", "ом", "ем", "ою", "ею"):
            if lower.endswith(ending) and len(lower) - len(ending) >= 3:
                word = word[: -len(ending)]
                break
        else:
            if lower[-1:] in "аяуюіїе" and len(lower) > 3:
                word = word[:-1]
        words.append(word)
    return " ".join(words)


_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g", "д": "d", "е": "e", "є": "ie", "ж": "zh",
    "з": "z", "и": "y", "і": "i", "ї": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ь": "", "ю": "iu", "я": "ia", "'": "", "ы": "y", "э": "e",
}


def translit(text: str) -> str:
    """Кирилиця -> латиниця для порівняння назв: 'джарвіс' -> 'jarvis', 'телеграм' -> 'telegram'."""
    text = text.lower().replace("дж", "j")
    return "".join(_TRANSLIT.get(ch, ch) for ch in text)


def best_match(query: str, candidates: list[str], cutoff: float = 0.6) -> str | None:
    """Найсхожіша назва зі списку (враховує кирилицю/латиницю і часткові збіги)."""
    q = query.lower().strip()
    variants = {q, translit(q)}
    best, best_score = None, 0.0
    for cand in candidates:
        c = cand.lower()
        score = max(SequenceMatcher(None, v, c).ratio() for v in variants)
        if any(v and v in c for v in variants):
            # часткові збіги: чим коротша назва, тим ближче вона до запиту ("chrome" -> "google chrome")
            score = max(score, 0.8 + 0.2 * min(len(v) for v in variants) / len(c))
        if c in variants:
            score = 1.0
        if score > best_score:
            best, best_score = cand, score
    return best if best_score >= cutoff else None


# Русизми й суржик, що проскакують у командах: "открой браузер" = "відкрий браузер".
SYNONYMS = {
    "открой": "відкрий", "откройте": "відкрий", "закрой": "закрий", "закройте": "закрий", "найди": "знайди",
    "поищи": "пошукай", "включи": "увімкни", "выключи": "вимкни", "сделай": "зроби", "громче": "гучніше",
    "тише": "тихіше", "громкость": "гучність", "сколько": "скільки", "время": "часу",
    "новости": "новини", "заметку": "нотатку", "заметки": "нотатки", "компьютер": "комп'ютер",
    "приложение": "додаток", "программу": "програму", "страницу": "сторінку", "следующая": "наступна",
    "следующую": "наступну", "предыдущая": "попередня", "перезагрузи": "перезавантаж",
    "сверни": "згорни", "разверни": "розгорни", "скриншот": "скріншот",
}
# Текст, набраний в англійській розкладці замість української: "dslrhbq" -> "відкрий".
_LAYOUT = str.maketrans(
    "qwertyuiop[]asdfghjkl;'zxcvbnm,.`",
    "йцукенгшщзхїфівапролджєячсмитьбю'",
)


def fix_layout(text: str) -> str:
    return text.lower().translate(_LAYOUT)


def edit_distance(a: str, b: str, limit: int = 2) -> int:
    """Кількість одруківок між словами (пропущена, зайва, замінена чи переставлена літера).
    Якщо більше за limit — повертає limit + 1, не дораховуючи."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev2, prev = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            if prev2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > limit:
            return limit + 1
        prev2, prev = prev, cur
    return min(prev[-1], limit + 1)


def correct_words(text: str, words: set[str], stems: set[str]) -> str:
    """Виправляє одруківки й суржик за словником команд: "відкрй браузер" -> "відкрий браузер".
    words — цілі слова з команд, stems — основи ("відкри" з "відкри\\w*"). Знайомі слова не чіпає."""
    out = []
    for word in text.split():
        word = SYNONYMS.get(word, word)
        if (len(word) < 4 or not word.replace("'", "").isalpha() or word in words
                or any(word.startswith(s) for s in stems if len(s) >= 3)):
            out.append(word)
            continue
        limit = 1 if len(word) <= 6 else 2
        best, best_d = word, limit + 1
        for w in words:
            if len(w) >= 3:
                d = edit_distance(word, w, limit)
                if d < best_d:
                    best, best_d = w, d
        for s in stems:
            if len(s) >= 4:
                stem_limit = min(limit, 1 if len(s) <= 6 else 2)
                for k in (len(s) - 1, len(s), len(s) + 1):
                    if k <= len(word):
                        d = edit_distance(word[:k], s, stem_limit)
                        if d <= stem_limit and d < best_d:
                            best, best_d = s + word[k:], d
        out.append(best)
    return " ".join(out)


def speakable(text: str, max_sentences: int | None = 2, max_chars: int = 400) -> str:
    """Готує markdown-текст до озвучення: прибирає код, посилання, символи розмітки."""
    t = re.sub(r"```.*?```", " (код) ", text, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"[#*_>|]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if max_sentences:
        t = " ".join(re.split(r"(?<=[.!?])\s+", t)[:max_sentences])
    return t[:max_chars]
