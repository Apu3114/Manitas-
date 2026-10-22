import math

# Indices de MediaPipe: (punta, articulacion media) de cada dedo
FINGERS = [(8, 6), (12, 10), (16, 14), (20, 18)]  # indice, medio, anular, menique
WRIST = 0

# Patron de dedos extendidos (indice, medio, anular, menique) -> token
PATTERNS = {
    (0, 0, 0, 0): "CONFIRM",     # puño
    (1, 0, 0, 0): "VOL_UP",      # solo indice
    (1, 1, 0, 0): "VOL_DOWN",    # indice y medio
    (1, 1, 1, 0): "OPEN_APP",    # tres dedos (critico)
    (1, 1, 1, 1): "PLAY_PAUSE",  # mano abierta
}


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def extended_fingers(landmarks):
    """Un dedo esta extendido si su punta queda mas lejos de la muñeca que su articulacion media."""
    wrist = landmarks[WRIST]
    return tuple(
        1 if _dist(landmarks[tip], wrist) > _dist(landmarks[pip], wrist) else 0
        for tip, pip in FINGERS
    )


def classify(landmarks):
    return PATTERNS.get(extended_fingers(landmarks))