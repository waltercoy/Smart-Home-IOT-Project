import cv2

backends = [
    ("ANY",  cv2.CAP_ANY),
    ("DSHOW", cv2.CAP_DSHOW),
    ("MSMF", cv2.CAP_MSMF)
]

for name, backend in backends:
    print(f"\n=== Testing backend: {name} ===")
    for idx in range(0, 4):   # try camera index 0..3
        print(f"  Trying index {idx}...", end=" ")
        cap = cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            print("❌ fail")
        else:
            ret, frame = cap.read()
            if ret:
                print("✅ success")
            else:
                print("⚠️ opened but no frame")
            cap.release()
