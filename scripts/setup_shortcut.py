"""Створює ярлик "Jarvis" у меню Пуск із гарячою клавішею запуску (за замовчуванням Ctrl+Alt+J).

Windows сама запускає програму за гарячою клавішею ярлика, якщо ярлик лежить у меню Пуск.
Джарвіс запускається без вікна консолі; журнал — у %LOCALAPPDATA%\\Jarvis\\jarvis.log.
Використання: python scripts/setup_shortcut.py [гаряча клавіша, напр. "Ctrl+Alt+J"]
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # папка проєкту, де лежить main.py
SHORTCUT = Path(os.environ["APPDATA"]) / r"Microsoft\Windows\Start Menu\Programs\Jarvis.lnk"


def main() -> None:
    hotkey = sys.argv[1] if len(sys.argv) > 1 else "Ctrl+Alt+J"
    pythonw = ROOT / ".venv" / "Scripts" / "pythonw.exe"
    script = f"""
$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{SHORTCUT}')
$s.TargetPath = '{pythonw}'
$s.Arguments = '"{ROOT / "main.py"}"'
$s.WorkingDirectory = '{ROOT}'
$s.Hotkey = '{hotkey}'
$s.Description = 'Jarvis — голосовий асистент'
$s.Save()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True)
    print(f"Ярлик створено: {SHORTCUT}\nГаряча клавіша запуску: {hotkey}")


if __name__ == "__main__":
    main()
