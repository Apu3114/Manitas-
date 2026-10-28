import math

# Indices de MediaPipe: (punta, articulacion media) de cada dedo
FINGERS = [(8, 6), (12, 10), (16, 14), (20, 18)]  # indice, medio, anular, menique
WRIST = 0

# Patron de dedos extendidos (indice, medio, anular, menique) -> token
PATTERNS = {
    (0, 0, 0, 0): "CONFIRM",      # puño
    (1, 0, 0, 0): "VOL_UP",       # solo indice
    (1, 1, 0, 0): "VOL_DOWN",     # indice y medio
    (1, 1, 1, 0): "OPEN_APP",     # tres dedos (critico)
    (1, 1, 1, 1): "PLAY_PAUSE",   # mano abierta
    # --- nuevas para ventanas ---
    (1, 0, 1, 0): "MOVE_UP",      # indice + anular
    (0, 1, 0, 1): "MOVE_DOWN",    # medio + menique
    (1, 0, 0, 1): "MOVE_LEFT",    # indice + menique ("rock")
    (0, 1, 1, 0): "MOVE_RIGHT",   # medio + anular (V central)
    (0, 0, 0, 1): "POSITION",     # solo menique -> siguiente posicion predefinida
    (0, 1, 0, 0): "CLOSE_WINDOW", # solo medio (critico)
    (0, 0, 1, 1): "MINIMIZE",     # anular + menique (critico)
}

# --- Pinza pulgar + indice (agarra y arrastra ventanas) -----------------
# Indices MediaPipe relevantes
THUMB_TIP = 4
THUMB_MCP = 2     # base del pulgar (CMC)
INDEX_TIP = 8
INDEX_MCP = 5     # nudillo base del indice
MIDDLE_MCP = 9    # centro de la palma (ancla del arrastre)

PINCH_CLOSE_RATIO = 0.55   # angar más cerca de esto = pinza cerrada (agarra)
PINCH_OPEN_RATIO = 0.75    # separar más de esto = pinza abierta (suelta)
PINCH_TREND_RATIO = 0.95   # si además se acerca rapido a la pinza, bloquea otros gestos
TREND_DELTA = 0.03

def _thumb_near_index(landmarks):
    """Distancia pulgar-indice normalizada por el tamaño de la mano (invariante a distancia de camara)."""
    size = max(1e-6, _dist(landmarks[WRIST], landmarks[MIDDLE_MCP]))
    return _dist(landmarks[THUMB_TIP], landmarks[INDEX_TIP]) / size


def pinch_ratio(landmarks):
    return _thumb_near_index(landmarks)


def pinch_closed(landmarks):
    """Pinza cerrada: pulgar muy cerca del indice y por encima del nudillo del indice.

    El chequeo 'pulgar arriba del nudillo' descarta el gesto de solo indice
    (VOL_UP) donde el pulgar suele quedar recogido por debajo de la mano.
    """
    return (
        pinch_ratio(landmarks) < PINCH_CLOSE_RATIO
        and landmarks[THUMB_TIP].y < landmarks[INDEX_MCP].y
    )


def pinch_open(landmarks):
    """Pinza claramente abierta (histéresis: suelta con un umbral mas alto del que agarra)."""
    return (
        pinch_ratio(landmarks) > PINCH_OPEN_RATIO
        or landmarks[THUMB_TIP].y >= landmarks[INDEX_MCP].y
    )


def pinch_closing(landmarks, prev_ratio):
    """True mientras la pinza se esta cerrando (sirve para silenciar otros gestos)."""
    ratio = pinch_ratio(landmarks)
    return ratio < PINCH_TREND_RATIO and ratio <= prev_ratio - TREND_DELTA


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def thumb_extended(landmarks):
    """Pulgar estirado fuera de la palma: la punta queda mas lejos de la muñeca que la base."""
    return _dist(landmarks[THUMB_TIP], landmarks[WRIST]) > _dist(landmarks[THUMB_MCP], landmarks[WRIST])


def extended_fingers(landmarks):
    """Un dedo esta extendido si su punta queda mas lejos de la muñeca que su articulacion media."""
    wrist = landmarks[WRIST]
    return tuple(
        1 if _dist(landmarks[tip], wrist) > _dist(landmarks[pip], wrist) else 0
        for tip, pip in FINGERS
    )


def classify(landmarks, prev_ratio=None):
    if landmarks is None:
        return None
    if prev_ratio is not None and pinch_closing(landmarks, prev_ratio):
        # El pulgar+indice se estan acercando: el agarre tiene prioridad y no
        # se dejan que los patrones de dedos (VOL_UP, MOVE_*) disparen solapados.
        return None
    if thumb_extended(landmarks):
        return "MAXIMIZE"
    return PATTERNS.get(extended_fingers(landmarks))