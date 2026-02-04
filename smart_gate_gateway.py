import cv2
import serial
import time
import json
import re

import paho.mqtt.client as mqtt
import firebase_admin
from firebase_admin import credentials, db

# ================= CONFIG =================
SERIAL_PORT = "COM5"
BAUD = 9600

CAM_INDEX = 0
CAM_BACKEND = cv2.CAP_MSMF

CONF_THRESHOLD = 70   # LBPH: smaller = more confident

# Debounce recognition (stabil)
ON_FRAMES = 3
OFF_FRAMES = 6

# Publish rate limit (biar smooth)
MQTT_INTERVAL = 0.5      # seconds
FIREBASE_INTERVAL = 1.5  # seconds

MQTT_HOST = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_BASE = "aiu/gate/aria"

SERVICE_ACCOUNT = "serviceAccountKey.json"
FIREBASE_DB_URL = "https://iotproj-767e8-default-rtdb.asia-southeast1.firebasedatabase.app/"

# ================= FIREBASE =================
cred = credentials.Certificate(SERVICE_ACCOUNT)
firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
db_ref = db.reference("gate_logs")

# ================= MQTT =================
client = mqtt.Client()
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()
print("✅ MQTT connected")

def mqtt_pub(topic, payload):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload)
    client.publish(f"{MQTT_BASE}/{topic}", payload)

# ================= SERIAL =================
ser = serial.Serial(SERIAL_PORT, BAUD, timeout=1)
time.sleep(2)
print("✅ Serial connected (close Arduino Serial Monitor)")

# ================= FACE MODEL =================
recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read("face_model.yml")

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# ================= CAMERA =================
cam = cv2.VideoCapture(CAM_INDEX, CAM_BACKEND)
if not cam.isOpened():
    print("❌ Cannot open camera")
    ser.close()
    raise SystemExit

# Optional: reduce camera load
cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

# Arduino CSV: DIST,12,OWNER,1,PIR,1,GATE,1
csv_pat = re.compile(r"^DIST,(\d+),OWNER,([01]),PIR,([01]),GATE,([01])$")

# Debounce vars
true_count = 0
false_count = 0
stable_owner = False
last_sent = None

# Rate limit vars
last_mqtt = 0
last_fb = 0

print("System running... Press q to exit")

try:
    while True:
        # ---------- CAMERA ----------
        ret, frame = cam.read()
        if not ret:
            print("❌ Can't read camera frame")
            break

        # To reduce CPU, you can detect every 2–3 frames (optional)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        owner_now = False
        best_box = None
        best_text = "NO FACE"
        best_conf = None

        for (x, y, w, h) in faces:
            face = gray[y:y+h, x:x+w]
            face = cv2.resize(face, (200, 200))

            label, conf = recognizer.predict(face)
            is_owner = (label == 1 and conf < CONF_THRESHOLD)

            if is_owner:
                owner_now = True

            # show best (lowest conf)
            if best_conf is None or conf < best_conf:
                best_conf = conf
                best_box = (x, y, w, h)
                best_text = ("Aria" if is_owner else "Unknown") + f" ({conf:.1f})"

        # ---------- OWNER DEBOUNCE ----------
        if owner_now:
            true_count += 1
            false_count = 0
        else:
            false_count += 1
            true_count = 0

        if (not stable_owner) and true_count >= ON_FRAMES:
            stable_owner = True
        if stable_owner and false_count >= OFF_FRAMES:
            stable_owner = False

        # ---------- SEND OWNER TO ARDUINO ----------
        to_send = b'1' if stable_owner else b'0'
        if to_send != last_sent:
            ser.write(to_send)
            last_sent = to_send
            print("[SEND]", "OWNER=1" if stable_owner else "OWNER=0")

        # ---------- READ FROM ARDUINO ----------
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            m = csv_pat.match(line)
            if m:
                distance = int(m.group(1))
                owner_flag = bool(int(m.group(2)))
                pir_flag = bool(int(m.group(3)))
                gate_flag = bool(int(m.group(4)))

                event = {
                    "timestamp": int(time.time()),
                    "distance_cm": distance,
                    "owner": owner_flag,
                    "pir_motion": pir_flag,
                    "gate_open": gate_flag
                }

                print("[DATA]", event)

                now = time.time()

                # ---------- MQTT (rate limited) ----------
                if now - last_mqtt >= MQTT_INTERVAL:
                    mqtt_pub("distance_cm", distance)
                    mqtt_pub("owner", 1 if owner_flag else 0)
                    mqtt_pub("pir_motion", 1 if pir_flag else 0)
                    mqtt_pub("gate_open", 1 if gate_flag else 0)
                    mqtt_pub("event", event)
                    last_mqtt = now

                # ---------- Firebase (rate limited) ----------
                if now - last_fb >= FIREBASE_INTERVAL:
                    db_ref.push(event)
                    last_fb = now

        # ---------- DISPLAY ----------
        cv2.putText(frame, f"OWNER: {'YES' if stable_owner else 'NO'}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    (255, 255, 255), 2)

        if best_box is not None:
            x, y, w, h = best_box
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 255), 2)
            cv2.putText(frame, best_text, (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (255, 255, 255), 2)

        cv2.imshow("Recognition", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    cam.release()
    ser.close()
    client.loop_stop()
    client.disconnect()
    cv2.destroyAllWindows()
    print("Stopped.")
