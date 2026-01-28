import cv2
import serial
import time
import threading

# ==========================
# CONFIG
# ==========================
ARDUINO_PORT = "COM5"   # GANTI sesuai port Arduino kamu
BAUD_RATE = 9600

CAM_INDEX = 0           # GANTI kalau pakai kamera lain (0 / 1 / 2)
CAM_BACKEND = cv2.CAP_MSMF   # Sama seperti yang berhasil di test_cam.py

# (opsional) untuk kalkulasi status gate di terminal
GATE_THRESHOLD_CM = 10   # samakan dengan THRESHOLD_CM di Arduino

# ==========================
# CONNECT TO ARDUINO
# ==========================
print(f"Connecting to Arduino on {ARDUINO_PORT}...")
ser = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=1)
time.sleep(2)
print("Connected to Arduino ✅")

# ==========================
# THREAD: READ FROM ARDUINO
# ==========================
arduino_distance = None
arduino_owner = None   # hanya untuk info dari print Arduino

def read_arduino():
    global arduino_distance, arduino_owner
    while True:
        try:
            line = ser.readline().decode(errors="ignore").strip()
        except Exception:
            line = ""
        if line:
            print(f"[ARD] {line}")
            if "Distance:" in line:
                # contoh: "Distance: 18 cm | Owner: YES"
                try:
                    parts = line.split('|')
                    dist_part = parts[0].split(':')[1].replace('cm', '').strip()
                    owner_part = parts[1].split(':')[1].strip()

                    arduino_distance = dist_part
                    arduino_owner = owner_part
                except Exception:
                    pass

# mulai thread pembaca serial
threading.Thread(target=read_arduino, daemon=True).start()

# ==========================
# OPEN CAMERA
# ==========================
cap = cv2.VideoCapture(CAM_INDEX, CAM_BACKEND)

if not cap.isOpened():
    print("❌ Cannot open camera")
    ser.close()
    exit()

# Load face detector
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# ===== Smoothing state owner =====
FACE_ON_FRAMES  = 5    # berapa frame berturut-turut ada muka -> YES
FACE_OFF_FRAMES = 10   # berapa frame berturut-turut tanpa muka -> NO

face_on_count = 0
face_off_count = 0
cam_owner = False      # status owner versi kamera (stabil)

last_gate_status = None   # supaya [STATUS] tidak spam

print("Camera ready. Press 'q' to quit.")

# ==========================
# MAIN LOOP
# ==========================
while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Can't receive camera frame")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    # --- update counter on/off ---
    if len(faces) > 0:
        face_on_count += 1
        face_off_count = 0
    else:
        face_off_count += 1
        face_on_count = 0

    # --- NO -> YES (stabil) ---
    if (not cam_owner) and face_on_count >= FACE_ON_FRAMES:
        cam_owner = True
        ser.write(b'1')
        print("[CAM] Owner: YES (stable)")

    # --- YES -> NO (stabil) ---
    if cam_owner and face_off_count >= FACE_OFF_FRAMES:
        cam_owner = False
        ser.write(b'0')
        print("[CAM] Owner: NO (stable)")

    # gambar kotak di wajah (debug)
    for (x, y, w, h) in faces:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), 2)

    cv2.imshow("Camera (press q to quit)", frame)

    # ---- STATUS di terminal (tidak spam) ----
    if arduino_distance is not None:
        try:
            dist_val = float(arduino_distance)
        except ValueError:
            dist_val = None

        if dist_val is not None:
            gate_open = cam_owner and (dist_val <= GATE_THRESHOLD_CM)
            gate_status = "OPEN" if gate_open else "CLOSED"
            status_str = f"Distance={dist_val} cm | Owner={'YES' if cam_owner else 'NO'} | Gate={gate_status}"

            if status_str != last_gate_status:
                print(f"[STATUS] {status_str}")
                last_gate_status = status_str

    # keluar kalau tekan 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# ==========================
# CLEANUP
# ==========================
cap.release()
ser.close()
cv2.destroyAllWindows()
print("Closed.")
