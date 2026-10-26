"""Інтерфейс у консолі: просто друкує розмову і коли Джарвіс почав/перестав слухати."""


class ConsoleUI:
    has_window = False

    def __init__(self):
        self._listening = None

    def log(self, who: str, text: str) -> None:
        print(f"{who}: {text}")

    def show(self) -> None:
        pass

    def view(self, mode: str) -> None:
        pass

    def status(self, state: str) -> None:
        if state in ("listen", "sleep") and (state == "listen") != self._listening:
            self._listening = state == "listen"
            print("[слухаю...]" if self._listening else "[не слухаю]")
