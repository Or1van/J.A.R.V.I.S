"""Вікно Джарвіса: індикатор стану, журнал розмови, кнопка "Говорити" і поле для тексту.

Tkinter працює в головному потоці, асистент — у фоновому. Асистент лише кладе
повідомлення в чергу, а вікно забирає їх кожні 50 мс — так потоки не заважають одне одному.
"""
import math
import queue
import tkinter as tk

BG = "#0b1220"
PANEL = "#111a2e"
FG = "#d8e6ff"
DIM = "#6b7c99"
ACCENT = "#28d7ff"

STATES = {
    "sleep": ("#2b3a52", "Не слухаю. Натисніть {hotkey} або «Говорити»"),
    "listen": (ACCENT, "Слухаю..."),
    "busy": ("#ffb020", "Виконую..."),
    "speak": ("#4cff9a", "Говорю..."),
}


class Hud:
    def __init__(self, assistant, hotkey: str):
        self.assistant = assistant
        self.hotkey = " і ".join(f"«{k}»" for k in hotkey.split("+"))
        self.queue: queue.Queue = queue.Queue()
        self.state = "sleep"
        self.phase = 0.0

        root = self.root = tk.Tk()
        root.title("J.A.R.V.I.S.")
        root.geometry("380x580")
        root.minsize(320, 440)
        root.configure(bg=BG)
        root.attributes("-topmost", True)

        tk.Label(root, text="J.A.R.V.I.S.", bg=BG, fg=ACCENT, font=("Segoe UI", 16, "bold")).pack(pady=(14, 0))
        self.canvas = tk.Canvas(root, width=170, height=170, bg=BG, highlightthickness=0)
        self.canvas.pack(pady=6)
        self.status_label = tk.Label(root, bg=BG, fg=DIM, font=("Segoe UI", 10), wraplength=340)
        self.status_label.pack(pady=(0, 8))

        # Нижня панель пакується до журналу, щоб журнал не витіснив її за край вікна.
        bottom = tk.Frame(root, bg=BG)
        bottom.pack(side="bottom", fill="x", padx=12, pady=10)
        self.entry = tk.Entry(bottom, bg=PANEL, fg=FG, insertbackground=FG, relief="flat", font=("Segoe UI", 10))
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", self._send_text)
        tk.Button(bottom, text="Говорити", command=self._activate, bg=ACCENT, fg=BG, relief="flat",
                  activebackground="#7fe8ff", font=("Segoe UI", 10, "bold"), cursor="hand2"
                  ).pack(side="right", padx=(8, 0), ipadx=8, ipady=2)

        self.log_box = tk.Text(root, bg=PANEL, fg=FG, relief="flat", wrap="word", font=("Segoe UI", 10),
                               padx=10, pady=8, state="disabled", height=8, highlightthickness=0)
        self.log_box.tag_configure("you", foreground=ACCENT)
        self.log_box.tag_configure("who", font=("Segoe UI", 10, "bold"))
        self.log_box.pack(fill="both", expand=True, padx=12)

        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(50, self._tick)

    # ---------- викликається з потоку асистента ----------

    def log(self, who: str, text: str) -> None:
        self.queue.put(("log", who, text))

    def status(self, state: str) -> None:
        self.queue.put(("status", state, None))

    def show(self) -> None:
        self.queue.put(("show", None, None))

    # ---------- потік вікна ----------

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        self.assistant.stop()
        self.root.destroy()

    def _activate(self) -> None:
        self.assistant.events.put(("jarvis.activate", {}))

    def _send_text(self, _event=None) -> None:
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, "end")
            self.assistant.events.put(("ui.text", {"text": text}))

    def _tick(self) -> None:
        if not self.assistant.running:
            self.root.destroy()
            return
        while True:
            try:
                kind, a, b = self.queue.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                self.state = a
            elif kind == "show":
                self.root.deiconify()
                self.root.lift()
            else:
                self._append(a, b)
        self.phase += 0.2
        self._draw()
        self.root.after(50, self._tick)

    def _append(self, who: str, text: str) -> None:
        tag = "you" if who == "Ви" else ""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{who}: ", ("who", tag))
        self.log_box.insert("end", f"{text}\n\n", (tag,))
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def _draw(self) -> None:
        """Малює "реактор": кільця пульсують і обертаються, коли Джарвіс активний."""
        color, label = STATES.get(self.state, STATES["sleep"])
        c = self.canvas
        c.delete("all")
        cx = cy = 85
        active = self.state != "sleep"
        pulse = (math.sin(self.phase) + 1) / 2 if active else 0.0
        r = 72 + 6 * pulse
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=2)
        spin = math.degrees(self.phase * 0.3) if active else 0.0
        for i in range(10):
            c.create_arc(cx - 58, cy - 58, cx + 58, cy + 58, start=i * 36 + spin, extent=22,
                         style="arc", outline=color, width=5)
        c.create_oval(cx - 38, cy - 38, cx + 38, cy + 38, outline=color, width=2)
        core = 20 + 4 * pulse
        c.create_oval(cx - core, cy - core, cx + core, cy + core, fill=color, outline="")
        self.status_label.configure(text=label.format(hotkey=self.hotkey), fg=color if active else DIM)
