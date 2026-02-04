import cv2
import os

cam = cv2.VideoCapture(0)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

os.makedirs("dataset/aria", exist_ok=True)

count = 0
while True:
    ret, frame = cam.read()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    for (x,y,w,h) in faces:
        count += 1
        cv2.imwrite(f"dataset/aria/{count}.jpg", gray[y:y+h, x:x+w])
        cv2.rectangle(frame,(x,y),(x+w,y+h),(255,255,255),2)
        cv2.imshow("Capturing", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
    if count >= 100:
        break

cam.release()
cv2.destroyAllWindows()
