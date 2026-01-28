import cv2

# Try default camera, with Windows backend
cap = cv2.VideoCapture(0, cv2.CAP_MSMF)  # coba 0 dulu


if not cap.isOpened():
    print("❌ Cannot open camera")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Can't receive frame")
        break

    cv2.imshow("Test Camera - press q to quit", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
