from enum import Enum

SIMPLE = {"VOL_UP", "VOL_DOWN", "PLAY_PAUSE", "FORWARD", "BACK", "MAXIMIZE",
          "MOVE_LEFT", "MOVE_RIGHT", "MOVE_UP", "MOVE_DOWN", "POSITION"}
CRITICAL = {"OPEN_APP", "CLOSE_WINDOW", "MINIMIZE"}
CONFIRM = "CONFIRM"

# Tokens que se repiten si se mantiene el gesto hecho (como apretar una tecla)
REPEAT = {"MOVE_LEFT", "MOVE_RIGHT", "MOVE_UP", "MOVE_DOWN"}
REPEAT_DELAY = 0.4  # segundos entre repeticiones


class State(Enum):
    IDLE = "Reposo"
    CANDIDATE = "Candidato"
    AWAITING = "Esperando confirmacion"


class GestureAutomaton:
    """Recibe un token por fotograma (o None) y decide cuando se acepta un comando."""

    def __init__(self, stable_frames=5, confirm_timeout=3.0):
        self.stable_frames = stable_frames
        self.confirm_timeout = confirm_timeout
        self._candidate = None
        self._count = 0
        self._latched = None   # token ya aceptado mientras se sigue sosteniendo
        self._pending = None   # comando critico esperando confirmacion
        self._deadline = 0.0
        self._last_emit = 0.0

    @property
    def state(self):
        if self._pending is not None:
            return State.AWAITING
        if self._candidate is not None and self._latched != self._candidate:
            return State.CANDIDATE
        return State.IDLE

    def feed(self, token, now):
        if self._pending is not None and now > self._deadline:
            self._pending = None
        if token is None:
            self._candidate, self._count, self._latched = None, 0, None
            return None
        if token != self._candidate:
            self._candidate, self._count, self._latched = token, 0, None
        self._count += 1
        if self._count < self.stable_frames:
            return None
        if self._latched == token:
            # Solo los tokens de REPETITION reemiten mientras se sostienen
            if token in REPEAT and now - self._last_emit >= REPEAT_DELAY:
                self._last_emit = now
                return self._accept(token, now)
            return None
        self._latched = token
        self._last_emit = now
        return self._accept(token, now)

    def _accept(self, token, now):
        if self._pending is not None:
            if token == CONFIRM:
                command, self._pending = self._pending, None
                return command
            self._pending = None  # cualquier otro gesto cancela
            return None
        if token in SIMPLE:
            return token
        if token in CRITICAL:
            self._pending = token
            self._deadline = now + self.confirm_timeout
        return None