import cv2

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    raise SystemExit("No se pudo abrir la camara")

while True:
    ok, frame = cap.read()
    if not ok:
        break
    cv2.imshow("Camara", cv2.flip(frame, 1))
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()