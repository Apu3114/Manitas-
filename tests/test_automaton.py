from automaton.automaton import GestureAutomaton, SIMPLE, State


def run(a, token, n, t=0.0):
    out = None
    for _ in range(n):
        r = a.feed(token, t)
        if r:
            out = r
    return out


def test_simple_needs_stable_frames():
    a = GestureAutomaton(stable_frames=3)
    assert run(a, "VOL_UP", 2) is None
    assert a.feed("VOL_UP", 0) == "VOL_UP"


def test_holding_does_not_repeat():
    a = GestureAutomaton(stable_frames=3)
    assert run(a, "VOL_UP", 3) == "VOL_UP"
    assert run(a, "VOL_UP", 10) is None


def test_critical_needs_confirm():
    a = GestureAutomaton(stable_frames=3)
    assert run(a, "OPEN_APP", 3) is None
    assert a.state == State.AWAITING
    assert run(a, "CONFIRM", 3) == "OPEN_APP"
    assert a.state == State.IDLE


def test_timeout_returns_to_idle():
    a = GestureAutomaton(stable_frames=3, confirm_timeout=3.0)
    run(a, "OPEN_APP", 3, t=0)
    assert run(a, "CONFIRM", 3, t=10) is None
    assert a.state == State.IDLE


def test_noise_resets_counter():
    a = GestureAutomaton(stable_frames=3)
    run(a, "VOL_UP", 2)
    a.feed(None, 0)
    assert run(a, "VOL_UP", 2) is None


def test_other_gesture_cancels_pending():
    a = GestureAutomaton(stable_frames=3)
    run(a, "OPEN_APP", 3)
    assert run(a, "VOL_UP", 3) is None
    assert a.state == State.IDLE
    assert run(a, "CONFIRM", 3) is None


def test_direction_repeats_while_held():
    a = GestureAutomaton(stable_frames=3)
    assert run(a, "MOVE_LEFT", 3, t=0) == "MOVE_LEFT"
    # se mantiene el gesto: no deberia reemitir antes del tiempo minimo
    assert run(a, "MOVE_LEFT", 6, t=0.2) is None
    # pasado el delay, vuelve a emitir sin cambiar de gesto
    assert run(a, "MOVE_LEFT", 1, t=0.5) == "MOVE_LEFT"


def test_other_hold_tokens_never_repeat():
    a = GestureAutomaton(stable_frames=3)
    assert run(a, "POSITION", 3) == "POSITION"
    assert run(a, "POSITION", 10) is None


def test_minimize_is_critical():
    a = GestureAutomaton(stable_frames=3)
    assert run(a, "MINIMIZE", 3) is None
    assert a.state == State.AWAITING
    assert run(a, "CONFIRM", 3) == "MINIMIZE"


def test_direction_gap_resets():
    a = GestureAutomaton(stable_frames=3)
    assert run(a, "MOVE_UP", 5) == "MOVE_UP"
    a.feed(None, 0)
    assert run(a, "MOVE_UP", 2) is None


def test_maximize_is_simple_and_emits_once():
    # MAXIMIZE es una accion simple: no requiere confirmacion critica
    # ni repetir mientras se sostiene el gesto.
    assert "MAXIMIZE" in SIMPLE
    a = GestureAutomaton(stable_frames=3)
    assert run(a, "MAXIMIZE", 2) is None
    assert run(a, "MAXIMIZE", 3) == "MAXIMIZE"
    assert a.state == State.IDLE
    assert run(a, "MAXIMIZE", 10) is None