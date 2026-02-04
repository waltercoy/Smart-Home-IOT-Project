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

CONF_THRESHOLD = 70  # LBPH confidence threshold (smaller = better match)

# ✅ session (after PIR motion)
SESSION_SECONDS = 20

# Owner stability (avoid True/False flicker)
ON_FRAMES = 3
OFF_FRAMES = 6

# Publish/log rate limits (smooth)
MQTT_INTERVAL = 0.5
FIREBASE_INTERVAL = 1.5

MQTT_HOST = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_BASE = "aiu/gate/aria"

SERVICE_ACCOUNT = "serviceaccountkey.json"
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

# Arduino CSV:
# DIST,12,PIR,1,SESSION,1,OWNER,0,GATE,0
csv_pat = re.compile(
    r"^DIST,(\d+),PIR,([01]),SESSION,([01]),OWNER,([01]),GATE,([01])$"
)

# ================= FACE MODEL =================
recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read("face_model.yml")

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# ================= CAMERA =================
cam = cv2.VideoCapture(CAM_INDEX, CAM_BACKEND)
cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cam.isOpened():
    ser.close()
    raise RuntimeError("❌ Cannot open camera")

print("📷 Camera ready")

# ================= STATE =================
# data from Arduino
distance_cm = None
pir_motion = False
arduino_session = False
arduino_owner = False
gate_open = False

# session logic in Python
session_active = False
session_until = 0  # epoch time

# owner debounce from camera
stable_owner = False
true_count = 0
false_count = 0

# last sent commands to Arduino
last_owner_cmd = None
last_session_cmd = None

# rate limit
last_mqtt = 0
last_fb = 0

def send_owner(owner_bool: bool):
    global last_owner_cmd
    cmd = b"O1" if owner_bool else b"O0"
    if cmd != last_owner_cmd:
        ser.write(cmd)
        last_owner_cmd = cmd
        print("[SEND]", cmd.decode())

def send_session(sess_bool: bool):
    global last_session_cmd
    cmd = b"S1" if sess_bool else b"S0"
    if cmd != last_session_cmd:
        ser.write(cmd)
        last_session_cmd = cmd
        print("[SEND]", cmd.decode())

print("System running (Session 20s). Press q to exit")

try:
    while True:
        # ---------- 1) read Arduino line ----------
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            m = csv_pat.match(line)
            if m:
                distance_cm = int(m.group(1))
                pir_motion = bool(int(m.group(2)))
                arduino_session = bool(int(m.group(3)))
                arduino_owner = bool(int(m.group(4)))
                gate_open = bool(int(m.group(5)))

        now = time.time()

        # ---------- 2) PIR triggers session ----------
        if pir_motion:
            session_active = True
            session_until = now + SESSION_SECONDS

        # session timeout
        if session_active and now > session_until:
            session_active = False

        # ---------- 3) camera recognition (only when session active) ----------
        if session_active:
            ret, frame = cam.read()
            if not ret:
                print("❌ Can't read camera frame")
                continue

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

                if best_conf is None or conf < best_conf:
                    best_conf = conf
                    best_box = (x, y, w, h)
                    best_text = ("Aria" if is_owner else "Unknown") + f" ({conf:.1f})"

            # debounce owner
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

            # show UI
            remain = max(0, int(session_until - now))
            cv2.putText(frame, f"SESSION: {remain}s",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (255, 255, 255), 2)

            cv2.putText(frame, f"OWNER: {'YES' if stable_owner else 'NO'}",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (255, 255, 255), 2)

            if best_box is not None:
                x, y, w, h = best_box
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 255), 2)
                cv2.putText(frame, best_text, (x, y-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                            (255, 255, 255), 2)

            cv2.imshow("Recognition", frame)

        else:
            # session off -> owner forced false (avoid open gate outside session)
            stable_owner = False
            true_count = 0
            false_count = 0

            # optionally hide window
            try:
                cv2.destroyWindow("Recognition")
            except:
                pass

        # ---------- 4) send session + owner to Arduino ----------
        send_session(session_active)
        send_owner(stable_owner)

        # ---------- 5) publish/log ----------
        if distance_cm is not None:
            event = {
                "timestamp": int(now),
                "distance_cm": distance_cm,
                "pir_motion": pir_motion,
                "session_active": session_active,
                "owner": stable_owner,
                "gate_open": gate_open,
                "lamp_on": gate_open

            }

            # print console status
            print("[DATA]", event)

            if now - last_mqtt >= MQTT_INTERVAL:
                mqtt_pub("distance_cm", distance_cm)
                mqtt_pub("pir_motion", 1 if pir_motion else 0)
                mqtt_pub("session_active", 1 if session_active else 0)
                mqtt_pub("owner", 1 if stable_owner else 0)
                mqtt_pub("gate_open", 1 if gate_open else 0)
                mqtt_pub("lamp_on", int(gate_open))
                mqtt_pub("event", event)
                last_mqtt = now

            if now - last_fb >= FIREBASE_INTERVAL:
                db_ref.push(event)
                last_fb = now

        # ---------- 6) quit ----------
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    cam.release()
    ser.close()
    client.loop_stop()
    client.disconnect()
    cv2.destroyAllWindows()
    print("Stopped.")
