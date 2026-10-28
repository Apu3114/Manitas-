import subprocess

import pyautogui

from windowcontrol import windowcontrol

pyautogui.PAUSE = 0


def _press(key, times=1):
    return lambda: pyautogui.press(key, presses=times)


def _step(dx, dy):
    """Mueve la ventana activa `dx`/`dy` pasos de ~100 px."""
    return lambda: windowcontrol.window_step(windowcontrol.foreground_hwnd(), dx, dy)


ACTIONS = {
    "VOL_UP": _press("volumeup", 5),
    "VOL_DOWN": _press("volumedown", 5),
    "PLAY_PAUSE": _press("playpause"),
    "FORWARD": _press("nexttrack"),
    "BACK": _press("prevtrack"),
    "MAXIMIZE": lambda: windowcontrol.maximize_foreground(windowcontrol.foreground_hwnd()),
    "OPEN_APP": lambda: subprocess.Popen("calc.exe"),
    # --- ventanas ---
    "MOVE_LEFT": _step(-1, 0),
    "MOVE_RIGHT": _step(1, 0),
    "MOVE_UP": _step(0, -1),
    "MOVE_DOWN": _step(0, 1),
    "POSITION": lambda: windowcontrol.apply_preset(windowcontrol.foreground_hwnd()),
    "MINIMIZE": windowcontrol.minimize_foreground,
    "CLOSE_WINDOW": windowcontrol.close_foreground,
}


def execute(command):
    action = ACTIONS.get(command)
    if action:
        action()