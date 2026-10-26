"""Вікно Джарвіса у трьох виглядах:
  - normal — компактне вікно: «реактор», журнал розмови, поле для тексту;
  - full   — повний екран (F11, подвійний клік по реактору, «Джарвіс, розгорнись»): великий реактор,
             годинник, стан комп'ютера й журнал;
  - mini   — коли вікно згорнуте, у кутку екрана лишається маленький анімований реактор
             (клік — розгорнути, перетягнути — перемістити, права кнопка — меню).

Tkinter працює в головному потоці, асистент — у фоновому. Асистент лише кладе
повідомлення в чергу, а вікно забирає їх кожні 40 мс — так потоки не заважають одне одному.
Вікно з'являється одразу, ще до завантаження моделей; асистента під'єднують пізніше (attach).
"""
import ctypes
import math
import queue
import time
import tkinter as tk
from datetime import datetime

import psutil

BG = "#050b14"
PANEL = "#0a1524"
LINE = "#16324d"
FG = "#d8e6ff"
DIM = "#5f7896"
ACCENT = "#28d7ff"
KEY = "#010203"  # колір, який у міні-реакторі стає прозорим
FONT = "Bahnschrift"
TEXT_FONT = "Segoe UI"

STATES = {
    "boot": ("#3a78b0", "Завантажуюсь..."),
    "sleep": ("#2f5f8a", "Не слухаю. Натисніть {hotkey} або «Говорити»"),
    "listen": (ACCENT, "Слухаю..."),
    "busy": ("#ffb020", "Виконую..."),
    "speak": ("#4cff9a", "Говорю..."),
}
WEEKDAYS = ("понеділок", "вівторок", "середа", "четвер", "п'ятниця", "субота", "неділя")
MONTHS = ("січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня",
          "вересня", "жовтня", "листопада", "грудня")
MINI_SIZE = 112


def mix(a: str, b: str, t: float) -> str:
    """Колір між a і b (t=0 — a, t=1 — b). Tkinter не вміє прозорість, тож «тьмяне» = змішане з фоном."""
    t = max(0.0, min(1.0, t))
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def draw_reactor(c: tk.Canvas, cx: float, cy: float, r: float, state: str, phase: float, bg: str = BG) -> None:
    """Малює «дуговий реактор» радіуса r з тегом dyn. Кожен стан має свою анімацію:
    сон — ледь дихає, слухає — сканер і хвилі, виконує — швидкі дуги, говорить — еквалайзер."""
    color = STATES.get(state, STATES["sleep"])[0]
    active = state not in ("sleep", "boot")
    if not active:
        color = mix(bg, color, 0.75)
    pulse = (math.sin(phase * (2.4 if active else 0.8)) + 1) / 2
    spin = phase * (40 if active else 6)
    if state == "busy":
        spin *= 3
    w = max(1, round(r / 60))

    def ring(rad, outline, width=1, **kw):
        c.create_oval(cx - rad, cy - rad, cx + rad, cy + rad, outline=outline, width=width, tags="dyn", **kw)

    def arc(rad, start, extent, outline, width):
        c.create_arc(cx - rad, cy - rad, cx + rad, cy + rad, start=start, extent=extent, style="arc",
                     outline=outline, width=width, tags="dyn")

    # Світіння навколо ядра
    for i, k in enumerate((0.62, 0.52, 0.44, 0.38)):
        c.create_oval(cx - r * k, cy - r * k, cx + r * k, cy + r * k, outline="",
                      fill=mix(bg, color, 0.05 + 0.05 * i + 0.05 * pulse), tags="dyn")

    # Шкала з рисками
    tick_color = mix(bg, color, 0.45)
    for i in range(60):
        a = math.radians(i * 6 + spin * 0.15)
        inner = r * (0.90 if i % 5 else 0.85)
        c.create_line(cx + inner * math.cos(a), cy + inner * math.sin(a), cx + r * math.cos(a), cy + r * math.sin(a),
                      fill=tick_color, width=w, tags="dyn")
    ring(r * 0.80, mix(bg, color, 0.35), w)

    # Сегментоване кільце й зустрічні дуги
    for i in range(12):
        arc(r * 0.72, i * 30 + spin, 18, color, max(2, round(r * 0.07)))
    for i in range(3):
        arc(r * 0.60, i * 120 - spin * 1.6, 70, mix(bg, color, 0.8), max(1, w + 1))
    ring(r * 0.50, mix(bg, color, 0.6), w)

    if state == "listen":
        arc(r * 0.88, -spin * 2.5, 40, color, max(2, w * 2))  # сканер
        for k in range(2):  # хвилі, що розходяться
            t = (phase * 0.6 + k / 2) % 1
            ring(r * (0.5 + 0.5 * t), mix(color, bg, t), w)
    elif state == "busy":
        for i in range(8):
            arc(r * 0.88, i * 45 + spin * 2, 12, color, max(2, w * 2))
    elif state == "speak":  # «еквалайзер» навколо ядра
        for i in range(36):
            a = math.radians(i * 10 + spin * 0.3)
            amp = 0.5 + 0.5 * math.sin(phase * 9 + i * 1.7) * math.sin(phase * 3.1 + i * 0.6)
            r1, r2 = r * 0.40, r * (0.42 + 0.06 * amp)
            c.create_line(cx + r1 * math.cos(a), cy + r1 * math.sin(a), cx + r2 * math.cos(a), cy + r2 * math.sin(a),
                          fill=color, width=max(1, w + 1), tags="dyn")

    # Ядро з трикутником, як у Mark II
    core = r * (0.30 + 0.025 * pulse)
    ring(core, mix(color, "#ffffff", 0.3), w + 1, fill=color)
    tri = []
    for i in range(3):
        a = math.radians(-90 + i * 120 - spin * 0.4)
        tri += [cx + core * 0.8 * math.cos(a), cy + core * 0.8 * math.sin(a)]
    c.create_polygon(tri, outline=mix(color, bg, 0.55), fill="", width=max(1, w + 1), tags="dyn")
    inner = core * 0.38
    c.create_oval(cx - inner, cy - inner, cx + inner, cy + inner, outline="", fill=mix(color, "#ffffff", 0.75), tags="dyn")


class Hud:
    has_window = True

    def __init__(self, settings, events: queue.Queue):
        self.settings = settings
        self.events = events
        self.assistant = None
        self.hotkey = " і ".join(f"«{k}»" for k in settings.hotkey.split("+"))
        self.queue: queue.Queue = queue.Queue()
        self.state = "boot"
        self.view_mode = "normal"
        self.restore_to = "normal"  # куди повертатись із міні-реактора
        self.started = time.time()
        self.stats: dict[str, float] = {}
        self.stats_at = 0.0
        self.last_reply = ""

        try:  # чіткий текст при масштабі Windows 125–150% замість розмитого
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
        root = self.root = tk.Tk()
        self.k = root.winfo_fpixels("1i") / 96  # 1.25 при масштабі 125%
        u = self.u
        root.title("J.A.R.V.I.S.")
        root.geometry(f"{u(420)}x{u(660)}")
        root.minsize(u(340), u(480))
        root.configure(bg=BG)
        root.attributes("-topmost", True)

        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)

        self.log_box = tk.Text(root, bg=PANEL, fg=FG, relief="flat", wrap="word", font=(TEXT_FONT, 10),
                               padx=u(12), pady=u(10), state="disabled", highlightthickness=1,
                               highlightbackground=LINE, highlightcolor=LINE, cursor="arrow")
        self.log_box.tag_configure("you", foreground=ACCENT)
        self.log_box.tag_configure("who", font=(TEXT_FONT, 10, "bold"))
        self.log_box.tag_configure("time", foreground=DIM, font=(TEXT_FONT, 8))

        self.bottom = tk.Frame(root, bg=BG)
        self.entry = tk.Entry(self.bottom, bg=PANEL, fg=FG, insertbackground=ACCENT, relief="flat",
                              font=(TEXT_FONT, 10), highlightthickness=1, highlightbackground=LINE,
                              highlightcolor=ACCENT)
        self.entry.pack(side="left", fill="both", expand=True, ipady=u(7))
        self.entry.bind("<Return>", self._send_text)
        self.talk = tk.Button(self.bottom, text="Говорити", command=self._activate, bg=ACCENT, fg=BG,
                              relief="flat", activebackground="#7fe8ff", font=(TEXT_FONT, 10, "bold"), cursor="hand2")
        self.talk.pack(side="right", fill="y", padx=(u(8), 0), ipadx=u(10))

        self._build_mini()

        self.canvas.bind("<Configure>", lambda _e: self._layout())
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.tag_bind("btn_full", "<Button-1>", lambda _e: self.toggle_full())
        self.canvas.tag_bind("btn_mini", "<Button-1>", lambda _e: self._set_view("mini"))
        root.bind("<F11>", lambda _e: self.toggle_full())
        root.bind("<Escape>", lambda _e: self._set_view("normal") if self.view_mode == "full" else None)
        root.bind("<Unmap>", self._on_unmap)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(40, self._tick)
        if settings.window_mode in ("full", "mini"):
            root.after(200, lambda: self._set_view(settings.window_mode))

    def u(self, v: float) -> int:
        """Розмір у пікселях з урахуванням масштабу екрана (розкладка задана для 100%)."""
        return round(v * self.k)

    # ---------- викликається з потоку асистента ----------

    def attach(self, assistant) -> None:
        self.assistant = assistant

    def log(self, who: str, text: str) -> None:
        print(f"{who}: {text}")
        self.queue.put(("log", who, text))

    def status(self, state: str) -> None:
        self.queue.put(("status", state, None))

    def show(self) -> None:
        self.queue.put(("show", None, None))

    def view(self, mode: str) -> None:
        """normal | full | mini — для голосових команд «розгорнись», «згорнись»."""
        self.queue.put(("view", mode, None))

    # ---------- потік вікна ----------

    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        if self.assistant:
            self.assistant.stop()
        self.root.destroy()

    def toggle_full(self) -> None:
        self._set_view("normal" if self.view_mode == "full" else "full")

    def _activate(self) -> None:
        self.events.put(("jarvis.activate", {}))

    def _send_text(self, _event=None) -> None:
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, "end")
            self.events.put(("ui.text", {"text": text}))

    def _on_double_click(self, event) -> None:
        cx, cy, r = getattr(self, "reactor_at", (0, 0, 0))
        if math.hypot(event.x - cx, event.y - cy) <= r:
            self.toggle_full()

    def _set_view(self, mode: str) -> None:
        root = self.root
        if mode == "mini":
            if self.view_mode != "mini":
                self.restore_to = self.view_mode
            self.view_mode = "mini"
            root.withdraw()
            self.mini.deiconify()
            self.mini.lift()
            return
        self.mini.withdraw()
        self.view_mode = mode
        root.deiconify()
        full = mode == "full"
        root.attributes("-fullscreen", full)
        root.attributes("-topmost", not full)  # на весь екран не заважаємо Alt+Tab
        root.lift()
        root.focus_force()
        self.log_box.configure(font=(TEXT_FONT, 11 if full else 10))
        self._layout()

    def _on_unmap(self, event) -> None:
        # Згорнули вікно кнопкою «_» або Win+D — показуємо міні-реактор замість кнопки на панелі задач
        if event.widget is self.root and self.root.state() == "iconic":
            self._set_view("mini")

    def _restore(self) -> None:
        self._set_view(self.restore_to if self.restore_to != "mini" else "normal")

    def _tick(self) -> None:
        if self.assistant is not None and not self.assistant.running:
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
                if self.view_mode == "mini":
                    self._restore()
                else:
                    self.root.deiconify()
                    self.root.lift()
            elif kind == "view":
                self._set_view(a)
            else:
                self._append(a, b)
        phase = time.time() - self.started
        if self.view_mode == "mini":
            self._draw_mini(phase)
        else:
            self._draw(phase)
        self.root.after(40, self._tick)

    def _append(self, who: str, text: str) -> None:
        tag = "you" if who == "Ви" else ""
        if who != "Ви":
            self.last_reply = text
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{datetime.now():%H:%M}  ", ("time",))
        self.log_box.insert("end", f"{who}: ", ("who", tag))
        self.log_box.insert("end", f"{text}\n\n", (tag,))
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    # ---------- розкладка та статичні елементи ----------

    def _layout(self) -> None:
        """Розставляє журнал і поле вводу та перемальовує статичний фон під поточний розмір і вигляд."""
        c, u = self.canvas, self.u
        w, h = max(c.winfo_width(), 1), max(c.winfo_height(), 1)
        c.delete("static")
        if self.view_mode == "full":
            side = min(max(w * 0.30, u(380)), u(620))
            x = w - side - u(40)
            self.log_box.place(x=x, y=u(110), width=side, height=h - u(220))
            self.bottom.place(x=x, y=h - u(90), width=side, height=u(44))
            left = u(340)  # ліва колонка з годинником і станом ПК
            self.reactor_at = ((left + x) / 2, h / 2, min(h * 0.30, (x - left) / 2 - u(30)))
            self._draw_grid(w, h)
            c.create_text(x, u(92), text="ЖУРНАЛ РОЗМОВИ", anchor="sw", fill=DIM, font=(FONT, 10), tags="static")
            c.create_text(u(40), h - u(28), text="F11 / Esc — звичайне вікно", anchor="w", fill=mix(BG, DIM, 0.7),
                          font=(FONT, 9), tags="static")
        else:
            log_top = int(h * 0.50)
            self.log_box.place(x=u(14), y=log_top, width=w - u(28), height=h - log_top - u(66))
            self.bottom.place(x=u(14), y=h - u(52), width=w - u(28), height=u(38))
            r = min(w * 0.36, h * 0.17)
            self.reactor_at = (w / 2, u(54) + r * 1.05, r)
            c.create_text(u(18), u(24), text="J.A.R.V.I.S.", anchor="w", fill=ACCENT, font=(FONT, 15, "bold"),
                          tags="static")
        # Кнопки у верхньому правому куті: на весь екран / згорнути в міні-реактор
        inset = u(48) if self.view_mode == "full" else 0  # у повному екрані — всередині кутової рамки
        for i, (label, tag) in enumerate((("⛶", "btn_full"), ("—", "btn_mini"))):
            bx = w - u(22) - inset - i * u(34)
            c.create_text(bx, u(24) + inset, text=label, fill=DIM, font=(TEXT_FONT, 14), tags=("static", tag))
        for tag in ("btn_full", "btn_mini"):
            c.tag_bind(tag, "<Enter>", lambda _e, t=tag: (c.itemconfigure(t, fill=ACCENT), c.configure(cursor="hand2")))
            c.tag_bind(tag, "<Leave>", lambda _e, t=tag: (c.itemconfigure(t, fill=DIM), c.configure(cursor="")))

    def _draw_grid(self, w: int, h: int) -> None:
        c, u = self.canvas, self.u
        grid = mix(BG, LINE, 0.45)
        for x in range(0, w, u(48)):
            c.create_line(x, 0, x, h, fill=grid, tags="static")
        for y in range(0, h, u(48)):
            c.create_line(0, y, w, y, fill=grid, tags="static")
        # Кутові скоби
        L, m = u(46), u(18)
        for x, y, dx, dy in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            c.create_line(x, y + dy * L, x, y, x + dx * L, y, fill=ACCENT, width=u(2), tags="static")
        c.create_text(w / 2, u(40), text="J.A.R.V.I.S.", fill=ACCENT, font=(FONT, 26, "bold"), tags="static")
        c.create_text(w / 2, u(70), text="JUST A RATHER VERY INTELLIGENT SYSTEM", fill=DIM, font=(FONT, 9),
                      tags="static")

    # ---------- анімація ----------

    def _draw(self, phase: float) -> None:
        c = self.canvas
        c.delete("dyn")
        if not hasattr(self, "reactor_at"):
            return
        cx, cy, r = self.reactor_at
        color, label = STATES.get(self.state, STATES["sleep"])
        draw_reactor(c, cx, cy, r, self.state, phase)
        active = self.state not in ("sleep", "boot")
        status_font = (FONT, 13 if self.view_mode == "full" else 10)
        c.create_text(cx, cy + r + self.u(34 if self.view_mode == "full" else 20),
                      text=label.format(hotkey=self.hotkey), fill=color if active else DIM, font=status_font,
                      width=max(r * 2.6, self.u(300)), justify="center", tags="dyn")
        if self.view_mode == "full":
            self._draw_panel(phase)

    def _draw_panel(self, phase: float) -> None:
        """Ліва колонка повного екрана: годинник і стан комп'ютера."""
        c, u = self.canvas, self.u
        now = datetime.now()
        x, y = u(48), u(120)
        clock = c.create_text(x, y, text=f"{now:%H:%M}", anchor="nw", fill=FG, font=(FONT, 54), tags="dyn")
        right, top = c.bbox(clock)[2], c.bbox(clock)[1]
        c.create_text(right + u(6), top + u(16), text=f"{now:%S}", anchor="nw", fill=ACCENT, font=(FONT, 16), tags="dyn")
        c.create_text(x + u(4), y + u(82), text=f"{WEEKDAYS[now.weekday()]}, {now.day} {MONTHS[now.month - 1]}",
                      anchor="nw", fill=DIM, font=(FONT, 12), tags="dyn")

        if time.time() - self.stats_at > 1.5:
            self.stats_at = time.time()
            self.stats = {
                "ПРОЦЕСОР": psutil.cpu_percent(interval=None),
                "ПАМ'ЯТЬ": psutil.virtual_memory().percent,
                "ДИСК C": psutil.disk_usage("C:\\").percent,
            }
            battery = psutil.sensors_battery()
            if battery:
                self.stats["БАТАРЕЯ"] = battery.percent
        gy = y + u(150)
        for i, (name, value) in enumerate(self.stats.items()):
            gx, gyy, gr = x + u(52 + (i % 2) * 140), gy + u(52 + (i // 2) * 150), u(46)
            warn = value > 85 if name != "БАТАРЕЯ" else value < 20
            col = "#ff5a6a" if warn else ACCENT
            c.create_arc(gx - gr, gyy - gr, gx + gr, gyy + gr, start=-135, extent=-270, style="arc",
                         outline=mix(BG, LINE, 0.9), width=u(7), tags="dyn")
            c.create_arc(gx - gr, gyy - gr, gx + gr, gyy + gr, start=225, extent=-270 * value / 100, style="arc",
                         outline=col, width=u(7), tags="dyn")
            c.create_text(gx, gyy, text=f"{value:.0f}%", fill=FG, font=(FONT, 15), tags="dyn")
            c.create_text(gx, gyy + gr + u(16), text=name, fill=DIM, font=(FONT, 9), tags="dyn")

    # ---------- міні-реактор ----------

    def _build_mini(self) -> None:
        mini = self.mini = tk.Toplevel(self.root)
        mini.withdraw()
        mini.overrideredirect(True)
        mini.attributes("-topmost", True)
        mini.configure(bg=KEY)
        mini.attributes("-transparentcolor", KEY)
        size = self.mini_size = self.u(MINI_SIZE)
        pos = self.settings.mini_position
        if pos:
            x, y = pos
        else:
            x = self.root.winfo_screenwidth() - size - self.u(24)
            y = self.root.winfo_screenheight() - size - self.u(72)
        mini.geometry(f"{size}x{size}+{x}+{y}")
        self.mini_canvas = tk.Canvas(mini, width=size, height=size, bg=KEY, highlightthickness=0, cursor="hand2")
        self.mini_canvas.pack()
        self._drag = None
        self.mini_canvas.bind("<ButtonPress-1>", self._mini_press)
        self.mini_canvas.bind("<B1-Motion>", self._mini_move)
        self.mini_canvas.bind("<ButtonRelease-1>", self._mini_release)
        menu = self.mini_menu = tk.Menu(mini, tearoff=False, bg=PANEL, fg=FG, activebackground=ACCENT,
                                        activeforeground=BG, font=(TEXT_FONT, 10))
        menu.add_command(label="Говорити", command=self._activate)
        menu.add_command(label="Розгорнути", command=self._restore)
        menu.add_command(label="На весь екран", command=lambda: self._set_view("full"))
        menu.add_separator()
        menu.add_command(label="Закрити Джарвіса", command=self.close)
        self.mini_canvas.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

    def _mini_press(self, event) -> None:
        self._drag = (event.x_root, event.y_root, self.mini.winfo_x(), self.mini.winfo_y(), False)

    def _mini_move(self, event) -> None:
        if not self._drag:
            return
        sx, sy, wx, wy, moved = self._drag
        dx, dy = event.x_root - sx, event.y_root - sy
        if moved or abs(dx) + abs(dy) > 4:
            self._drag = (sx, sy, wx, wy, True)
            self.mini.geometry(f"+{wx + dx}+{wy + dy}")

    def _mini_release(self, _event) -> None:
        moved = self._drag and self._drag[4]
        self._drag = None
        if moved:
            self.settings.mini_position = [self.mini.winfo_x(), self.mini.winfo_y()]
            self.settings.save()
        else:
            self._restore()

    def _draw_mini(self, phase: float) -> None:
        c = self.mini_canvas
        c.delete("dyn")
        half = self.mini_size / 2
        r = half - self.u(6)
        color = STATES.get(self.state, STATES["sleep"])[0]
        pad = self.u(4)
        c.create_oval(half - r - pad, half - r - pad, half + r + pad, half + r + pad, fill=BG,
                      outline=mix(BG, color, 0.5), width=1, tags="dyn")
        draw_reactor(c, half, half, r, self.state, phase)
