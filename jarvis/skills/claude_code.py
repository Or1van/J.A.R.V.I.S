"""Claude Code голосом. Працює за вашою підпискою Claude — платний API не використовується.

"Джарвіс, відкрий Claude Code" -> вікно терміналу з Claude Code у проєкті, далі ви працюєте в ньому самі.
Коли Claude закінчить роботу або попросить дозволу, Джарвіс про це скаже
(це повідомляють хуки Claude Code, які Джарвіс підключає при запуску).
"Джарвіс, диктую" -> режим диктування: усе сказане записується й зачитується, "відправ" — іде в Claude Code.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


from jarvis.core import runtime
from jarvis.core.desktop import bring_to_front, find_window, paste_text, press
from jarvis.core.registry import OPEN, command, tool
from jarvis.core.text import is_no, is_yes, speakable, split_wake_word
from jarvis.paths import DATA_DIR, ROOT
from jarvis.skills.projects import find_project

WINDOW_TITLE = "Jarvis - Claude Code"
CLAUDE = r"(?:клод|claude|клауд)\w* (?:код|code|кот)"

SEND = r"(?:відправ|відправляй|надішли|надсилай|відправити|send|го)(?: це| завдання| його)?"
CLEAR = r"(?:очисти|видали все|скасуй все|почни спочатку|спочатку|скасуй)"
UNDO = r"(?:видали|прибери) (?:останнє|останню фразу|останній шматок)"
READ_DRAFT = r"(?:прочитай|що ти записав|що записав|повтори)(?: що записав| завдання| все)?"
READ_ANSWER = r"(?:прочитай|що) (?:відповідь|він відповів|клод відповів|відповів клод)"
EXIT = r"(?:вийди|вихід|закінчи|завершити|вийти)(?: з режиму| з клод код\w*)?|достатньо|режим звичайний"
APPROVE = r"(?:дозволяю|дозволь|дозволити|підтверджую|можна|так дозволяю)"
DENY = r"(?:забороняю|заборони|відхилити|відхили|не дозволяю)"


def find_claude() -> str | None:
    """claude у PATH або найновіша версія з розширення Claude Code для VS Code."""
    exe = shutil.which("claude")
    if exe:
        return exe
    ext_dir = Path.home() / ".vscode" / "extensions"

    def version(path: Path) -> tuple[int, ...]:
        m = re.search(r"claude-code-(\d+)\.(\d+)\.(\d+)", str(path))
        return tuple(int(x) for x in m.groups()) if m else (0,)

    found = sorted(ext_dir.glob("anthropic.claude-code-*/resources/native-binary/claude.exe"), key=version)
    return str(found[-1]) if found else None


def _hooks_settings() -> Path:
    """Файл налаштувань для Claude Code: хуки Stop і Notification повідомляють Джарвіса."""
    hooks_dir = DATA_DIR / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    # Копія скрипта лежить у шляху без кирилиці й пробілів — так надійніше для оболонки хуків.
    script = hooks_dir / "claude_code_hook.py"
    shutil.copyfile(ROOT / "jarvis" / "hooks" / "claude_code_hook.py", script)
    python = Path(getattr(sys, "_base_executable", sys.executable)).as_posix()
    port = runtime.settings().event_port

    def hook(kind: str) -> list:
        return [{"hooks": [{"type": "command", "command": f'"{python}" "{script.as_posix()}" {kind} {port}'}]}]

    settings_file = hooks_dir / "claude_code_settings.json"
    settings_file.write_text(json.dumps({"hooks": {"Stop": hook("stop"), "Notification": hook("notification")}}, indent=2))
    return settings_file


class ClaudeCodeSession:
    def __init__(self, project: Path):
        self.project = project
        self.pending_permission = False
        self.working = False
        self.last_answer = ""

    def launch(self) -> bool:
        exe = find_claude()
        if exe is None:
            return False
        args = [exe, "--settings", str(_hooks_settings())]
        if shutil.which("wt"):
            subprocess.Popen(["wt", "-w", "new", "--title", WINDOW_TITLE, "--suppressApplicationTitle",
                              "-d", str(self.project), *args])
        else:
            subprocess.Popen(["cmd", "/c", "start", WINDOW_TITLE, "/D", str(self.project), *args])
        for _ in range(40):  # чекаємо, поки з'явиться вікно (до 10 секунд)
            if self.window():
                return True
            time.sleep(0.25)
        return False

    def window(self):
        return find_window(WINDOW_TITLE) or find_window("claude code")

    def _focus(self) -> bool:
        win = self.window()
        return win is not None and bring_to_front(win)

    def send(self, text: str) -> bool:
        if not self._focus():
            return False
        paste_text(text)
        time.sleep(0.3)
        press("enter")
        self.working = True
        return True

    def answer_permission(self, allow: bool) -> bool:
        if not self._focus():
            return False
        press("enter" if allow else "esc")
        self.pending_permission = False
        return True


_session: ClaudeCodeSession | None = None


class DictationMode:
    """Режим диктування завдання для Claude Code.
    temporary=True — режим увімкнувся лише щоб відповісти на запит дозволу і вимкнеться після відповіді."""

    def __init__(self, temporary: bool = False):
        self.draft: list[str] = []
        self.temporary = temporary

    def handle(self, text: str, utterance) -> None:
        session = _session
        if session is None or session.window() is None:
            runtime.set_mode(None)
            runtime.say("Вікно Claude Code закрите. Виходжу з режиму.")
            return

        if session.pending_permission:
            allow = bool(re.fullmatch(APPROVE, text) or is_yes(text))
            if allow or re.fullmatch(DENY, text) or is_no(text):
                session.answer_permission(allow)
                if self.temporary:
                    runtime.set_mode(None)
                runtime.say("Дозволив." if allow else "Відхилив.")
                return
            if self.temporary:
                runtime.say("Скажіть «дозволяю» або «ні».")
                return

        if re.fullmatch(SEND, text) or (self.draft and re.fullmatch(r"так|да|давай", text)):
            self.send()
        elif re.fullmatch(APPROVE, text):
            session.answer_permission(True)
        elif re.fullmatch(CLEAR, text):
            self.draft.clear()
            runtime.say("Очистив. Диктуйте заново.")
        elif re.fullmatch(UNDO, text):
            if self.draft:
                self.draft.pop()
            runtime.say("Прибрав останнє." if self.draft else "Завдання порожнє.")
        elif re.fullmatch(READ_ANSWER, text):
            runtime.say(speakable(session.last_answer, max_sentences=None, max_chars=1500) or "Відповіді ще немає.")
        elif re.fullmatch(READ_DRAFT, text):
            runtime.say(" ".join(self.draft) if self.draft else "Поки нічого не записано.")
        elif re.fullmatch(EXIT, text):
            runtime.set_mode(None)
            runtime.say("Виходжу з режиму Claude Code. Вікно лишається відкритим.")
        else:
            _, piece = split_wake_word(utterance.accurate(), runtime.settings().wake_words)
            self.draft.append(piece.strip())
            runtime.say(f"Записав: {piece}. Відправити?")

    def send(self) -> None:
        if not self.draft:
            runtime.say("Завдання порожнє. Спершу продиктуйте, що зробити.")
            return
        text = " ".join(self.draft)
        if _session and _session.send(text):
            self.draft.clear()
            runtime.say("Відправив. Скажу, коли Claude закінчить.")
        else:
            runtime.say("Не вдалося знайти вікно Claude Code.")


def start_session(project_name: str = "") -> str:
    global _session
    project = find_project(project_name)
    if project is None:
        return f"Не знайшов проєкт {project_name}." if project_name else "Не знайшов жодного проєкту."
    if _session and _session.project == project and _session.window():
        bring_to_front(_session.window())
        return "Claude Code уже відкритий."
    runtime.say(f"Відкриваю Claude Code у проєкті {project.name}.")
    session = ClaudeCodeSession(project)
    if not session.launch():
        return "Не вдалося запустити Claude Code."
    _session = session
    return "Claude Code готовий до роботи."


def start_dictation() -> str:
    if _session is None or _session.window() is None:
        return "Спершу відкрийте Claude Code."
    runtime.set_mode(DictationMode())
    return "Диктуйте, я запишу. Коли закінчите, скажіть «відправ»."


@tool
def claude_code_task(task: str, project: str = "") -> str:
    """Передати завдання з програмування в Claude Code — він працює прямо в папці проєкту
    (пише й виправляє код, створює файли, робить рев'ю). Коли закінчить, Джарвіс повідомить.

    Args:
        task: Детальний опис завдання для Claude Code.
        project: Назва проєкту (папки). Порожньо — останній проєкт.
    """
    reply = start_session(project)
    if _session is None or not _session.window():
        return reply
    time.sleep(2)  # даємо Claude Code завантажитись
    return "Завдання передано в Claude Code." if _session.send(task) else "Не вдалося передати завдання."


@command(rf"{OPEN} {CLAUDE}(?: (?:в|у|для) (?:проєкт\w*|проект\w*) (?P<project>.+))?", rf"{CLAUDE}", priority=7)
def _open_claude_code(project=""):
    return start_session(project)


@command(
    rf"(?:диктую|продиктую|диктуватиму|запиши|записуй)(?: завдання)?(?: для {CLAUDE}| (?:клод|claude)\w*)?|режим диктування",
    priority=7,
)
def _dictate():
    return start_dictation()


@runtime.on_event("claude_code.stop")
def _on_stop(payload: dict) -> None:
    if _session is None:
        return
    _session.working = False
    answer = payload.get("last_assistant_message") or _last_answer(payload.get("transcript_path"))
    _session.last_answer = answer or ""
    message = "Claude Code закінчив роботу."
    if runtime.settings().claude_code_summary and answer:
        message += " " + speakable(answer)
    runtime.say(message)


@runtime.on_event("claude_code.notification")
def _on_notification(payload: dict) -> None:
    if _session is None:
        return
    text = payload.get("message", "")
    if "permission" in text.lower():
        _session.pending_permission = True
        if not isinstance(runtime.assistant().mode, DictationMode):
            runtime.set_mode(DictationMode(temporary=True))
        tool_name = text.rsplit(" ", 1)[-1] if " to use " in text else ""
        runtime.say(f"Claude Code просить дозволу {('на ' + tool_name) if tool_name else 'на дію'}. "
                    "Скажіть «дозволяю» або «ні».")


def _last_answer(transcript_path: str | None) -> str:
    """Останній текст відповіді Claude з файлу розмови (JSONL)."""
    if not transcript_path or not Path(transcript_path).exists():
        return ""
    lines = Path(transcript_path).read_text(encoding="utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content", [])
        texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        if any(t.strip() for t in texts):
            return "\n".join(texts)
    return ""
