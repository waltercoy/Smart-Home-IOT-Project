import cv2
import serial
import time

# ===== CONNECT TO ARDUINO =====
ser = serial.Serial("COM5", 9600, timeout=1)  # GANTI COM PORT
time.sleep(2)

recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read("face_model.yml")

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

cam = cv2.VideoCapture(0)
ON_FRAMES = 3      # butuh 3 frame True untuk jadi ON
OFF_FRAMES = 6     # butuh 6 frame False untuk jadi OFF

true_count = 0
false_count = 0

stable_owner = False   # status final yang stabil
last_sent = None       # biar nggak spam

while True:
    ret, frame = cam.read()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    owner_detected = False

    for (x,y,w,h) in faces:
        face = gray[y:y+h, x:x+w]
        face = cv2.resize(face, (200, 200))  # PENTING (sama seperti training)

        label, confidence = recognizer.predict(face)

        if label == 1 and confidence < 70:
            owner_detected = True
            text = "Aria"
        else:
            text = "Unknown"

        cv2.putText(frame, text, (x, y-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
        cv2.rectangle(frame, (x, y), (x+w, y+h), (255,255,255), 2)
    

    # ===== INI KONEKSI KE ARDUINO =====
    # ===== smoothing / debounce =====
    if owner_detected:
        true_count += 1
        false_count = 0
    else:
        false_count += 1
        true_count = 0
    # naik jadi TRUE kalau konsisten beberapa frame
    if (not stable_owner) and true_count >= ON_FRAMES:
        stable_owner = True
    # turun jadi FALSE kalau konsisten beberapa frame
    if stable_owner and false_count >= OFF_FRAMES:
        stable_owner = False
    # ===== kirim ke Arduino hanya kalau berubah =====
    to_send = b'1' if stable_owner else b'0'
    if to_send != last_sent:
        ser.write(to_send)
        last_sent = to_send
    print("Owner raw:", owner_detected, "| Owner stable:", stable_owner)


    print("Owner:", owner_detected)

    cv2.imshow("Recognition", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cam.release()
ser.close()
cv2.destroyAllWindows()
