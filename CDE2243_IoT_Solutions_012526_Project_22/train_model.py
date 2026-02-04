import cv2
import os
import numpy as np

recognizer = cv2.face.LBPHFaceRecognizer_create()
faces = []
labels = []

label_id = 1  # label untuk "Aria"

for filename in os.listdir("dataset/aria"):
    img = cv2.imread(f"dataset/aria/{filename}", cv2.IMREAD_GRAYSCALE)
    faces.append(img)
    labels.append(label_id)

recognizer.train(faces, np.array(labels))
recognizer.save("face_model.yml")

print("Training done!")
