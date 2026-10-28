from recognizer.recognizer import (
    PINCH_CLOSE_RATIO,
    PINCH_OPEN_RATIO,
    classify,
    pinch_closed,
    pinch_open,
    pinch_ratio,
    thumb_extended,
)


class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y


def make_hand(thumb=None, index_tip=None, index_mcp=None, middle_mcp=None):
    """Mano sintética de 21 landmarks (solo se usan 0, 4, 5, 8 y 9)."""
    pts = [Point(0.5, 0.9)] + [Point(0.5, 0.85)] * 20
    pts[4] = thumb or Point(0.5, 0.62)     # punta del pulgar
    pts[5] = index_mcp or Point(0.5, 0.68)  # nudillo base del indice
    pts[8] = index_tip or Point(0.5, 0.60)  # punta del indice
    pts[9] = middle_mcp or Point(0.5, 0.70)  # centro de la palma
    return pts


def test_pinch_closed_when_thumb_and_index_touch():
    hand = make_hand(thumb=Point(0.5, 0.60), index_tip=Point(0.5, 0.62))
    ratio = pinch_ratio(hand)  # ~0.1 << 0.55
    assert ratio < PINCH_CLOSE_RATIO
    assert pinch_closed(hand) is True


def test_not_pinch_when_thumb_below_index_knuckle_like_vol_up():
    # Mano con indice arriba y pulgar recogido de la configuracion VOL_UP:
    # el pulgar queda por DEBAJO del nudillo del indice.
    hand = make_hand(thumb=Point(0.35, 0.82), index_tip=Point(0.5, 0.60))
    assert pinch_closed(hand) is False
    assert pinch_open(hand) is True  # separacion grande: pinza claramente abierta


def test_pinch_open_hysteresis_threshold_higher():
    hand = make_hand(thumb=Point(0.35, 0.60), index_tip=Point(0.65, 0.60))
    ratio = pinch_ratio(hand)
    assert ratio > PINCH_OPEN_RATIO
    assert pinch_open(hand) is True
    assert pinch_closed(hand) is False


def test_ratio_in_between_is_neither_closed_nor_open():
    # Zona de histeresis: ni cerro ni abrio, mantiene el estado anterior
    hand = make_hand(thumb=Point(0.44, 0.60), index_tip=Point(0.58, 0.60))
    ratio = pinch_ratio(hand)  # dist = 0.14, mano = 0.2 -> 0.7
    assert PINCH_CLOSE_RATIO <= ratio <= PINCH_OPEN_RATIO
    assert pinch_closed(hand) is False
    assert pinch_open(hand) is False


def test_ring_finger_only_has_no_token_anymore():
    # El patron (0,0,1,0) que era MOVE_MODE fue retirado (solo anular extendido)
    pts = [Point(0.5, 0.9)] + [Point(0.5, 0.85)] * 20
    pts[16] = Point(0.5, 0.5)  # anular: punta mas lejos de la muneca que su articulacion
    pts[14] = Point(0.5, 0.7)
    assert classify(pts) is None


def test_thumb_extended_returns_maximize():
    hand = make_hand()
    hand[2] = Point(0.5, 0.86)   # base del pulgar (CMC)
    hand[4] = Point(0.5, 0.30)   # punta del pulgar estirada
    for i in (6, 8, 10, 12, 14, 16, 18, 20):
        hand[i] = Point(0.5, 0.85)  # dedos doblados
    assert thumb_extended(hand) is True
    assert classify(hand) == "MAXIMIZE"


def test_thumb_folded_does_not_maximize():
    hand = make_hand()
    hand[2] = Point(0.55, 0.83)
    hand[4] = Point(0.52, 0.84)   # punta del pulgar pegada a la base: no estirado
    for i in (6, 8, 10, 12, 14, 16, 18, 20):
        hand[i] = Point(0.5, 0.85)  # dedos doblados
    assert thumb_extended(hand) is False
    assert classify(hand) != "MAXIMIZE"
