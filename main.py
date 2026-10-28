"""Intérprete de gestos.

Por defecto corre en segundo plano (sin ventana, sin consola).
Usa --show si en algún momento quieres volver a ver la detección.
Para detenerlo mientras corre oculto: Ctrl+Alt+Q (o stop_manitas.bat).
"""
import ctypes
import os
import sys
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

SHOW = "--show" in sys.argv

from recognizer.recognizer import classify  # noqa: E402
from automaton.automaton import GestureAutomaton  # noqa: E402
from actions.actions import execute  # noqa: E402
from windowcontrol.windowcontrol import WindowGrabber  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(BASE_DIR, "manitas.pid")

# --- Evitar dos instancias a la vez -----------------------------------
def _pid_alive(pid):
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x100000, False, int(pid))  # PROCESS_QUERY
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    except Exception:
        return False


if os.path.exists(PID_FILE) and not SHOW:
    try:
        old = int(open(PID_FILE).read().strip())
        if _pid_alive(old):
            sys.exit(0)  # ya hay un Manitas corriendo en segundo plano
    except Exception:
        pass
open(PID_FILE, "w").write(str(os.getpid()))


# --- Hotkey para cerrar en segundo plano: Ctrl+Alt+Q -------------------
user32 = ctypes.windll.user32
VK_Q, VK_CONTROL, VK_MENU = 0x51, 0x11, 0x12


def _quit_pressed():
    ctrl = user32.GetAsyncKeyState(VK_CONTROL) & 0x8000
    alt = user32.GetAsyncKeyState(VK_MENU) & 0x8000
    q = user32.GetAsyncKeyState(VK_Q) & 0x8000
    return ctrl and alt and q


# --- MediaPipe / cámara -----------------------------------------------
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
    sys.exit(1)

prev_grab = False
try:
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        try:
            result = landmarker.detect_for_video(image, int(time.monotonic() * 1000))
        except Exception:
            # Un frame con datos inconsistentes no debe tumbar el proceso en segundo plano.
            result = None

        # Pinza (pulgar + indice): agarrar/arrastrar/soltar ventanas.
        landmarks = result.hand_landmarks[0] if result and result.hand_landmarks else None
        grabber.feed(landmarks)
        now = time.monotonic()
        grabbing = grabber.active or grabber.suppress
        if grabbing != prev_grab:
            # Transicion de estado del gesto de agarre: limpiar el estado de
            # movimiento/confirmacion para que no arrastre latches de otros intentos.
            if grabbing:
                automaton.reset()
            prev_grab = grabbing
        if grabbing:
            # Mientras se cierra/agarra la pinza, el automata queda mudo para
            # que el indice levantado (VOL_UP) no se dispare por accidente.
            last_command, last_time = "ARRASTRANDO..." if grabber.active else "", now
            token = None
        else:
            token = classify(landmarks, grabber.prev_ratio) if landmarks else None

        command = automaton.feed(token, now)
        if command:
            last_command, last_time = command, now
            try:
                execute(command)
            except Exception:
                # Una accion fallida (p.ej. ventana cerrada mientras se mueve) no debe tumbar el bucle.
                pass

        if not SHOW and _quit_pressed():
            break

        if SHOW:
            h, w = frame.shape[:2]
            for hand in result.hand_landmarks:
                for p in hand:
                    cv2.circle(frame, (int(p.x * w), int(p.y * h)), 4, (0, 255, 0), -1)
            cv2.putText(frame, f"Token: {token}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame, f"Estado: {automaton.state.value}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            if not _quit_pressed():
                cv2.imshow("Intérprete de gestos", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
finally:
    cap.release()
    cv2.destroyAllWindows()
    try:
        os.remove(PID_FILE)
    except OSError:
        pass
