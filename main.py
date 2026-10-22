import time
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from recognizer.recognizer import classify
from automaton.automaton import GestureAutomaton
from actions.actions import execute

options = vision.HandLandmarkerOptions(
    base_options=python.BaseOptions(model_asset_path="hand_landmarker.task"),
    running_mode=vision.RunningMode.VIDEO,
    num_hands=1,
)
landmarker = vision.HandLandmarker.create_from_options(options)
automaton = GestureAutomaton(stable_frames=8, confirm_timeout=3.0)

last_command, last_time = "", 0.0
cap = cv2.VideoCapture(0)
while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect_for_video(image, int(time.monotonic() * 1000))

    token = classify(result.hand_landmarks[0]) if result.hand_landmarks else None
    now = time.monotonic()
    command = automaton.feed(token, now)
    if command:
        last_command, last_time = command, now
        execute(command)

    h, w = frame.shape[:2]
    for hand in result.hand_landmarks:
        for p in hand:
            cv2.circle(frame, (int(p.x * w), int(p.y * h)), 4, (0, 255, 0), -1)

    cv2.putText(frame, f"Token: {token}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"Estado: {automaton.state.value}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    if now - last_time < 2.0 and last_command:
        cv2.putText(frame, f"COMANDO: {last_command}", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

    cv2.imshow("Interprete de gestos", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()