"""Manitas: interfaz grafica del interprete de gestos (tema verde y negro).

Analizador lexico: el token que produce el reconocedor a partir de la mano.
Analizador sintactico: estado del automata y regla de la gramatica en uso.
Comandos ejecutados.
"""
import os
import queue
import sys
import threading
import time
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from recognizer.recognizer import classify
from automaton import automaton as automaton_module
from automaton.automaton import GestureAutomaton
from actions.actions import execute
from windowcontrol.windowcontrol import WindowGrabber

SIMPLE = set(getattr(automaton_module, "SIMPLE", set()))
CRITICAL = set(getattr(automaton_module, "CRITICAL", set()))
CONFIRM = getattr(automaton_module, "CONFIRM", "CONFIRM")

GRAMMAR = [
    ("Command", "Command  →  Simple  |  Critical CONFIRM"),
    ("Simple", "Simple   →  " + "  |  ".join(sorted(SIMPLE))),
    ("Critical", "Critical →  " + "  |  ".join(sorted(CRITICAL))),
]

# ---------- paleta ----------
BG = "#050805"          # negro de fondo
PANEL = "#0B120D"       # superficie de los recuadros
WELL = "#070D09"        # fondo de listas y gramatica
CHIP = "#101A13"        # etapas apagadas
BORDER = "#1B3A26"      # bordes
ACCENT = "#3DDC84"      # verde principal
ACCENT_DIM = "#1E7B46"  # verde apagado
TEXT = "#CFEBD8"        # texto
MUTED = "#6E9680"       # texto secundario
ALERT = "#E5484D"       # errores

UI = "Segoe UI"
MONO = "Consolas"


class Worker(threading.Thread):
    """Lee la camara, clasifica, alimenta el automata y avisa a la ventana."""

    def __init__(self, events):
        super().__init__(daemon=True)
        self.events = events
        self.stop_flag = threading.Event()

    def emit(self, **kw):
        self.events.put(kw)

    def run(self):
        cap = None
        try:
            options = vision.HandLandmarkerOptions(
                base_options=python.BaseOptions(
                    model_asset_path=os.path.join(BASE_DIR, "hand_landmarker.task")
                ),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
            )
            landmarker = vision.HandLandmarker.create_from_options(options)
            automaton = GestureAutomaton(stable_frames=8, confirm_timeout=3.0)
            grabber = WindowGrabber()

            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.emit(kind="error", text="No se pudo abrir la camara")
                return
            self.emit(kind="status", text="Cámara activa", ok=True)

            prev_grab = False
            last_view = None
            while not self.stop_flag.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                try:
                    result = landmarker.detect_for_video(image, int(time.monotonic() * 1000))
                except Exception:
                    result = None

                landmarks = result.hand_landmarks[0] if result and result.hand_landmarks else None
                grabber.feed(landmarks)
                now = time.monotonic()
                grabbing = grabber.active or grabber.suppress
                if grabbing != prev_grab:
                    if grabbing:
                        automaton.reset()
                    prev_grab = grabbing

                if grabbing:
                    token = None
                else:
                    token = classify(landmarks, grabber.prev_ratio) if landmarks else None

                command = automaton.feed(token, now)
                if command:
                    try:
                        execute(command)
                    except Exception:
                        pass
                    self.emit(kind="command", command=command)

                view = (token, automaton.state.value, landmarks is not None, grabber.active)
                if view != last_view:
                    self.emit(kind="frame", token=token, state=view[1],
                              hand=view[2], dragging=view[3])
                    last_view = view
        except Exception:
            self.emit(kind="error", text=traceback.format_exc())
        finally:
            if cap is not None:
                cap.release()
            self.emit(kind="status", text="Detenido", ok=False)


def make_panel(parent, title, subtitle):
    """Recuadro con borde verde tenue, titulo y una linea que explica su papel."""
    outer = tk.Frame(parent, bg=BORDER)
    inner = tk.Frame(outer, bg=PANEL)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    tk.Label(inner, text=title, bg=PANEL, fg=ACCENT, font=(UI, 12, "bold"),
             anchor="w").pack(fill="x", padx=14, pady=(12, 0))
    tk.Label(inner, text=subtitle, bg=PANEL, fg=MUTED, font=(UI, 9),
             anchor="w").pack(fill="x", padx=14)
    body = tk.Frame(inner, bg=PANEL)
    body.pack(fill="both", expand=True, padx=14, pady=(10, 14))
    return outer, body


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Manitas · Intérprete de gestos")
        self.geometry("860x660")
        self.minsize(760, 580)
        self.configure(bg=BG)

        self.events = queue.Queue()
        self.last_token = None
        self.flash_id = None
        self.topmost = tk.BooleanVar(value=False)

        self._style()
        self._build_menu()
        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.worker = Worker(self.events)
        self.worker.start()
        self.after(40, self.poll)

    # ---------- estilo ----------
    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Vertical.TScrollbar", background=BORDER, troughcolor=WELL,
                        bordercolor=WELL, arrowcolor=ACCENT, lightcolor=BORDER,
                        darkcolor=BORDER)
        style.map("Vertical.TScrollbar", background=[("active", ACCENT_DIM)])

    def _build_menu(self):
        opts = dict(tearoff=0, bg=PANEL, fg=TEXT, activebackground=ACCENT_DIM,
                    activeforeground=BG, borderwidth=0)
        menu = tk.Menu(self, **opts)
        archivo = tk.Menu(menu, **opts)
        archivo.add_command(label="Salir", command=self.close)
        menu.add_cascade(label="Archivo", menu=archivo)

        ver = tk.Menu(menu, **opts)
        ver.add_checkbutton(label="Siempre visible", variable=self.topmost,
                            command=lambda: self.attributes("-topmost", self.topmost.get()))
        ver.add_command(label="Limpiar registros", command=self.clear_logs)
        menu.add_cascade(label="Ver", menu=ver)

        ayuda = tk.Menu(menu, **opts)
        ayuda.add_command(label="Acerca de", command=lambda: messagebox.showinfo(
            "Acerca de",
            "Manitas\nIntérprete de gestos de la mano\n\n"
            "Cadena: gesto → token → regla → comando"))
        menu.add_cascade(label="Ayuda", menu=ayuda)
        self.config(menu=menu)

    # ---------- interfaz ----------
    def _build_ui(self):
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True, padx=18, pady=14)

        # Encabezado
        head = tk.Frame(root, bg=BG)
        head.pack(fill="x")
        tk.Label(head, text="Manitas", bg=BG, fg=ACCENT,
                 font=(UI, 24, "bold")).pack(side="left")
        tk.Label(head, text="  intérprete de gestos de la mano", bg=BG, fg=MUTED,
                 font=(UI, 11)).pack(side="left", pady=(10, 0))
        self.status_var = tk.StringVar(value="Iniciando")
        tk.Label(head, textvariable=self.status_var, bg=BG, fg=MUTED,
                 font=(UI, 10)).pack(side="right")
        self.dot = tk.Label(head, text="●", bg=BG, fg=ACCENT_DIM, font=(UI, 12))
        self.dot.pack(side="right", padx=(0, 6))

        # Cadena de traduccion: se ilumina la etapa activa
        chain = tk.Frame(root, bg=BG)
        chain.pack(fill="x", pady=(12, 12))
        self.stages = []
        for i, name in enumerate(["Mano", "Token", "Regla", "Comando"]):
            chip = tk.Label(chain, text=name, bg=CHIP, fg=MUTED, padx=18, pady=6,
                            font=(UI, 10, "bold"))
            chip.pack(side="left")
            self.stages.append(chip)
            if i < 3:
                tk.Label(chain, text="→", bg=BG, fg=ACCENT_DIM,
                         font=(UI, 12)).pack(side="left", padx=8)

        # Recuadros
        grid = tk.Frame(root, bg=BG)
        grid.pack(fill="both", expand=True)
        grid.columnconfigure(0, weight=1, uniform="c")
        grid.columnconfigure(1, weight=1, uniform="c")
        grid.rowconfigure(0, weight=3)
        grid.rowconfigure(1, weight=2)

        lex, lbody = make_panel(grid, "Analizador léxico",
                                "Convierte la posición de la mano en un token")
        lex.grid(row=0, column=0, sticky="nsew", padx=(0, 7), pady=(0, 14))
        self.token_var = tk.StringVar(value="—")
        self.token_lbl = tk.Label(lbody, textvariable=self.token_var, bg=PANEL, fg=MUTED,
                                  font=(MONO, 28, "bold"), anchor="w")
        self.token_lbl.pack(fill="x")
        self.hand_var = tk.StringVar(value="Sin mano")
        tk.Label(lbody, textvariable=self.hand_var, bg=PANEL, fg=MUTED,
                 font=(UI, 10), anchor="w").pack(fill="x", pady=(0, 8))
        self.token_log = self._make_list(lbody)

        syn, sbody = make_panel(grid, "Analizador sintáctico",
                                "Valida el token con la gramática y el autómata")
        syn.grid(row=0, column=1, sticky="nsew", padx=(7, 0), pady=(0, 14))
        self.state_var = tk.StringVar(value="—")
        tk.Label(sbody, textvariable=self.state_var, bg=PANEL, fg=TEXT,
                 font=(UI, 18, "bold"), anchor="w").pack(fill="x")
        tk.Label(sbody, text="Estado del autómata", bg=PANEL, fg=MUTED,
                 font=(UI, 9), anchor="w").pack(fill="x", pady=(0, 8))
        self.grammar = tk.Text(sbody, height=6, wrap="word", font=(MONO, 10), relief="flat",
                               bg=WELL, fg=TEXT, padx=8, pady=6, borderwidth=0,
                               highlightthickness=0, cursor="arrow")
        self.grammar.pack(fill="x")
        for _, line in GRAMMAR:
            self.grammar.insert("end", line + "\n")
        self.grammar.tag_configure("active", background=ACCENT, foreground=BG)
        self.grammar.config(state="disabled")
        tk.Label(sbody, text="Última derivación", bg=PANEL, fg=MUTED,
                 font=(UI, 9), anchor="w").pack(fill="x", pady=(10, 2))
        self.deriv_var = tk.StringVar(value="—")
        tk.Label(sbody, textvariable=self.deriv_var, bg=PANEL, fg=TEXT, justify="left",
                 font=(MONO, 10), anchor="w", wraplength=340).pack(fill="x")

        cmd, cbody = make_panel(grid, "Comandos ejecutados",
                                "Lo que el intérprete mandó hacer al sistema")
        cmd.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.cmd_log = self._make_list(cbody)

    def _make_list(self, parent):
        frame = tk.Frame(parent, bg=WELL)
        frame.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(frame, orient="vertical")
        lb = tk.Listbox(frame, yscrollcommand=sb.set, font=(MONO, 10), bg=WELL, fg=TEXT,
                        selectbackground=ACCENT_DIM, selectforeground=BG,
                        activestyle="none", borderwidth=0, highlightthickness=0)
        sb.config(command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        return lb

    # ---------- logica ----------
    def clear_logs(self):
        self.token_log.delete(0, "end")
        self.cmd_log.delete(0, "end")
        self.deriv_var.set("—")

    def _push(self, lb, text):
        lb.insert(0, f"{time.strftime('%H:%M:%S')}   {text}")
        if lb.size() > 200:
            lb.delete(200, "end")

    def _stage(self, i, on):
        if on:
            self.stages[i].config(bg=ACCENT, fg=BG)
        else:
            self.stages[i].config(bg=CHIP, fg=MUTED)

    def _flash_command(self):
        self._stage(3, True)
        if self.flash_id:
            self.after_cancel(self.flash_id)
        self.flash_id = self.after(1200, lambda: self._stage(3, False))

    def _highlight(self, token, state):
        self.grammar.config(state="normal")
        self.grammar.tag_remove("active", "1.0", "end")
        names = set()
        if token in SIMPLE:
            names |= {"Command", "Simple"}
        if token in CRITICAL:
            names |= {"Command", "Critical"}
        if token == CONFIRM:
            names |= {"Command"}
        if "Esperando" in state:
            names |= {"Command", "Critical"}
        for i, (name, _) in enumerate(GRAMMAR, start=1):
            if name in names:
                self.grammar.tag_add("active", f"{i}.0", f"{i}.end")
        self.grammar.config(state="disabled")

    def handle(self, ev):
        kind = ev["kind"]
        if kind == "frame":
            token = ev["token"]
            if ev["dragging"]:
                self.token_var.set("ARRASTRANDO")
            else:
                self.token_var.set(token if token else "—")
            self.token_lbl.config(fg=ACCENT if (token or ev["dragging"]) else MUTED)
            self.hand_var.set("Mano detectada" if ev["hand"] else "Sin mano")
            self.state_var.set(ev["state"])
            self._highlight(token, ev["state"])
            self._stage(0, ev["hand"])
            self._stage(1, bool(token) or ev["dragging"])
            self._stage(2, not ev["state"].lower().startswith("reposo"))
            if token and token != self.last_token:
                self._push(self.token_log, token)
            self.last_token = token
        elif kind == "command":
            cmd = ev["command"]
            self._push(self.cmd_log, cmd)
            self._flash_command()
            if cmd in CRITICAL:
                self.deriv_var.set(f"Command → Critical {CONFIRM}\n        → {cmd} {CONFIRM}")
            elif cmd in SIMPLE:
                self.deriv_var.set(f"Command → Simple\n        → {cmd}")
            else:
                self.deriv_var.set(f"Command → {cmd}")
        elif kind == "status":
            self.status_var.set(ev["text"])
            self.dot.config(fg=ACCENT if ev.get("ok") else MUTED)
        elif kind == "error":
            self.status_var.set("Error: revisa manitas_error.log")
            self.dot.config(fg=ALERT)
            with open(os.path.join(BASE_DIR, "manitas_error.log"), "a", encoding="utf-8") as f:
                f.write(ev["text"] + "\n")

    def poll(self):
        try:
            while True:
                self.handle(self.events.get_nowait())
        except queue.Empty:
            pass
        self.after(40, self.poll)

    def close(self):
        self.worker.stop_flag.set()
        self.worker.join(timeout=2)
        self.destroy()


if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception:
        with open(os.path.join(BASE_DIR, "manitas_error.log"), "a", encoding="utf-8") as f:
            f.write(traceback.format_exc() + "\n")
        raise