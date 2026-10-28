"""Control de ventanas del escritorio mediante la API de Windows (ctypes).

No hay dependencias externas: solo ctypes con user32.
- Acciones discretas (mover pasos, presets, minimizar, cerrar) operan sobre
  la "ventana activa" (la que esta en primer plano al llamarlas).
- WindowGrabber implementa el agarre por pinza (pulgar + indice): agarrar,
  arrastrar siguiendo la palma y, al soltar cerca de los bordes izquierdo o
  derecho, acoplar la ventana a media pantalla (snap).
"""
import ctypes

from ctypes import wintypes

from recognizer.recognizer import MIDDLE_MCP
from recognizer.recognizer import pinch_closed, pinch_closing, pinch_open, pinch_ratio

user32 = ctypes.windll.user32
SW_SHOWMINIMIZED = 2
SW_SHOWMAXIMIZED = 3
SW_RESTORE = 9
SW_MINIMIZE = 6
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
WM_CLOSE = 0x0010

WND = wintypes.HWND


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", POINT),
        ("ptMaxPosition", POINT),
        ("rcNormalPosition", RECT),
    ]


user32.SetWindowPos.argtypes = [WND, WND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.GetWindowRect.argtypes = [WND, ctypes.POINTER(RECT)]
user32.ShowWindow.argtypes = [WND, ctypes.c_int]
user32.GetWindowPlacement.argtypes = [WND, ctypes.POINTER(WINDOWPLACEMENT)]
user32.PostMessageW.argtypes = [WND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

# --- Consultas ----------------------------------------------------------


def screen_size():
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def work_area():
    """Escritorio util (sin barra de tareas): (left, top, width, height).

    SystemParametersInfoW(SPI_GETWORKAREA) falla silenciosamente en algunos
    entornos, asi que se calcula con GetSystemMetrics:
    SM_CX/CYFULLSCREEN describe la cliente de una ventana maximizada,
    equivalente al area util del monitor primario.
    """
    sw, sh = screen_size()
    h = user32.GetSystemMetrics(17)  # SM_CYFULLSCREEN
    if not (0 < h <= sh):
        h = sh
    return 0, 0, sw, h


def foreground_hwnd():
    return user32.GetForegroundWindow()


def get_rect(hwnd):
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def get_size(hwnd):
    left, top, right, bottom = get_rect(hwnd)
    return max(1, right - left), max(1, bottom - top)


def _placement(hwnd):
    wp = WINDOWPLACEMENT()
    wp.length = ctypes.sizeof(WINDOWPLACEMENT)
    user32.GetWindowPlacement(hwnd, ctypes.byref(wp))
    return wp


def is_maximized(hwnd):
    return _placement(hwnd).showCmd == SW_SHOWMAXIMIZED


def is_minimized(hwnd):
    return _placement(hwnd).showCmd == SW_SHOWMINIMIZED


# --- Acciones -----------------------------------------------------------


def ensure_restored(hwnd):
    """Si la ventana esta maximizada o minimizada, la restauramos para poder moverla."""
    show_cmd = _placement(hwnd).showCmd
    if show_cmd in (SW_SHOWMAXIMIZED, SW_SHOWMINIMIZED):
        user32.ShowWindow(hwnd, SW_RESTORE)
        return True
    return False


def move_window_to(hwnd, x, y):
    if is_maximized(hwnd):
        ensure_restored(hwnd)  # mover recupera el tamano normal
    user32.SetWindowPos(hwnd, 0, int(x), int(y), 0, 0,
                        SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)


def move_by(hwnd, dx, dy):
    left, top, _, _ = get_rect(hwnd)
    move_window_to(hwnd, left + dx, top + dy)


def window_step(hwnd, dx, dy, step=100):
    """Mueve la ventana `step` pixeles en una direccion."""
    move_by(hwnd, dx * step, dy * step)


_PRESETS = ("centro", "arriba-izq", "arriba-der", "abajo-der", "abajo-izq")
_preset_index = 0


def apply_preset(hwnd, index=None):
    """Coloca la ventana en una posicion predefinida del escritorio.

    Sin `index` avanza en ciclo por: centro -> arriba-izq -> arriba-der ->
    abajo-der -> abajo-izq -> centro ...  Devuelve el nombre del lugar.
    """
    global _preset_index
    if index is None:
        index, _preset_index = _preset_index, (_preset_index + 1) % len(_PRESETS)
    else:
        _preset_index = index
    sw, sh = screen_size()
    w, h = get_size(hwnd)
    pad = 40
    spots = {
        "centro": ((sw - w) // 2, (sh - h) // 2),
        "arriba-izq": (pad, pad),
        "arriba-der": (sw - w - pad, pad),
        "abajo-der": (sw - w - pad, sh - h - pad),
        "abajo-izq": (pad, sh - h - pad),
    }
    x, y = spots[_PRESETS[index]]
    move_window_to(hwnd, x, y)
    return _PRESETS[index]


def snap_half(hwnd, side):
    """Acopla la ventana a la mitad izquierda o derecha del area de trabajo."""
    wl, wt, ww, wh = work_area()
    x = wl if side == "left" else wl + ww // 2
    if is_maximized(hwnd):
        ensure_restored(hwnd)
    user32.SetWindowPos(hwnd, 0, int(x), int(wt), ww // 2, wh,
                        SWP_NOZORDER | SWP_NOACTIVATE)


def maximize_foreground(hwnd=None):
    """Maximiza la ventana (la activa si no se pasa un hwnd)."""
    if hwnd is None:
        hwnd = foreground_hwnd()
    if hwnd and not is_maximized(hwnd):
        user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)


def minimize_foreground():
    hwnd = foreground_hwnd()
    if hwnd:
        user32.ShowWindow(hwnd, SW_MINIMIZE)


def close_foreground():
    hwnd = foreground_hwnd()
    if hwnd:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


def minimize_window(hwnd):
    user32.ShowWindow(hwnd, SW_MINIMIZE)


# --- Agarre por pinza (pulgar + indice) ----------------------------------


class WindowGrabber:
    """Sistema de "tomar ventanas" con pinza de pulgar e indice.

    - 3 frames de pinza cerrada -> agarra la ventana activa y guarda el punto
      exacto donde la agarraste (la ventana no salta al ser tomada).
    - Mientras este cerrada la pinza, la ventana sigue la palma (landmark 9)
      con suavizado y zona muerta.
    - La pinza debe abrirse con demarcacion clara (histéresis) para soltar:
      exige frames consecutivos de pinza abierta.
    - Al soltar cerca del borde izquierdo o derecho del escritorio, la ventana
      se acopla a esa mitad (snap); soltado en el medio queda donde cae.
    - Se pierde la mano (camara/oclusion) mas de LOST_FRAMES -> suelta pacifico.

    Atributos siempre visibles:
        active    -> hay una ventana agarrada
        suppress  -> la pinza se esta cerrando o agarrada: silenciar el automata
    """

    ENTER_FRAMES = 3
    RELEASE_FRAMES = 3
    LOST_FRAMES = 8
    SNAP_ZONE = 0.18       # fraccion del area de trabajo que activa el snap
    SMOOTH = 0.45          # proporcion del salto que se aplica por frame
    DEADZONE = 5           # pixeles ignorados para no vibrar
    MAP_X = (0.05, 0.95)   # margenes de la camara mapeados a todo el ancho
    MAP_Y = (0.10, 0.95)

    def __init__(self):
        self.active = False
        self.suppress = False
        self._closed_count = 0
        self._open_count = 0
        self._lost = 0
        self._hwnd = None
        self._offset = (0, 0)
        self._last = (0, 0)
        self._win_w = self._win_h = 0
        self._prev_ratio = 99.0

    # --- utilidades ---
    @staticmethod
    def _point(landmarks):
        p = landmarks[MIDDLE_MCP]  # centro de la palma
        return p.x, p.y

    def _map(self, point):
        x0, x1 = self.MAP_X
        y0, y1 = self.MAP_Y
        kx = max(0.0, min(1.0, (point[0] - x0) / (x1 - x0)))
        ky = max(0.0, min(1.0, (point[1] - y0) / (y1 - y0)))
        sw, sh = screen_size()
        return kx * sw, ky * sh

    # --- maquina de estados ---
    def feed(self, landmarks):
        """Recibe los landmarks de la mano (o None) y devuelve `active`."""
        if landmarks is None:
            self._prev_ratio = 99.0
            if self.active:
                self._lost += 1
                if self._lost >= self.LOST_FRAMES:
                    self._drop(None)
            else:
                self._closed_count = 0
                self.suppress = False
            return self.active

        ratio = pinch_ratio(landmarks)

        if self.active:
            self.suppress = True
            self._lost = 0
            if pinch_closed(landmarks):
                self._open_count = 0
            elif pinch_open(landmarks):
                self._open_count += 1
                if self._open_count >= self.RELEASE_FRAMES:
                    self._drop(landmarks)
                    return self.active
            # (ratio intermedio: histéresis, no cuenta como abierto)
            self._drag(self._point(landmarks))
            return self.active

        # No hay ventana agarrada
        if pinch_closed(landmarks):
            self._closed_count += 1
            self.suppress = True
            if self._closed_count >= self.ENTER_FRAMES:
                self._grab(landmarks)
        else:
            self._closed_count = 0
            self.suppress = pinch_closing(landmarks, self._prev_ratio)
        self._prev_ratio = ratio
        return self.active

    # --- fases ---
    def _grab(self, landmarks):
        hwnd = foreground_hwnd()
        if not hwnd:
            return
        if is_maximized(hwnd):
            ensure_restored(hwnd)
        self._hwnd = hwnd
        self._win_w, self._win_h = get_size(hwnd)
        point = self._map(self._point(landmarks))
        left, top, _, _ = get_rect(hwnd)
        # el punto de la pantalla bajo la palma mantiene su desplazamiento
        self._offset = (left - point[0], top - point[1])
        self._last = (float(left), float(top))
        self.active = True
        self._open_count = self._closed_count = self._lost = 0

    def _drag(self, point):
        if self._hwnd is None or not user32.IsWindow(self._hwnd):
            self.active = False
            self.suppress = False
            return
        target_x, target_y = self._map(point)
        target_x += self._offset[0]
        target_y += self._offset[1]
        # no dejar la ventana fuera del escritorio
        sw, sh = screen_size()
        target_x = max(0, min(target_x, sw - self._win_w))
        target_y = max(0, min(target_y, sh - self._win_h))
        x = self._last[0] + self.SMOOTH * (target_x - self._last[0])
        y = self._last[1] + self.SMOOTH * (target_y - self._last[1])
        if abs(x - self._last[0]) < self.DEADZONE and abs(y - self._last[1]) < self.DEADZONE:
            return
        self._last = (x, y)
        move_window_to(self._hwnd, x, y)

    def _drop(self, landmarks):
        self.active = False
        self.suppress = False
        self._closed_count = self._open_count = self._lost = 0
        hwnd, self._hwnd = self._hwnd, None
        if not hwnd or not user32.IsWindow(hwnd):
            return
        if landmarks is None:
            return  # se perdio la mano: queda donde estaba
        wl, wt, ww, _ = work_area()
        point = self._map(self._point(landmarks))
        side_frac = (point[0] - wl) / max(1, ww)
        if side_frac < self.SNAP_ZONE:
            snap_half(hwnd, "left")
        elif side_frac > 1.0 - self.SNAP_ZONE:
            snap_half(hwnd, "right")
        else:
            move_window_to(hwnd, self._last[0], self._last[1])
