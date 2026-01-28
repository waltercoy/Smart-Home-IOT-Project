#include <Servo.h>

Servo gateServo;

// --- Pins ---
const int TRIG_PIN  = 10;
const int ECHO_PIN  = 11;
const int SERVO_PIN = 9;

const int LED1_PIN = 4;  // D4
const int LED2_PIN = 5;  // D5

// --- Settings ---
const int THRESHOLD_CM = 10;    // <= 3 cm to open gate
const int OPEN_ANGLE   = 90;
const int CLOSE_ANGLE  = 0;

// signal from PC camera (Python)
bool ownerDetected = false;

long readDistanceCM() {
  // Trigger pulse
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  // Read echo
  long duration = pulseIn(ECHO_PIN, HIGH, 30000); // timeout 30ms ~ 5m
  if (duration == 0) return 999; // no reading

  long cm = duration * 0.0343 / 2.0;
  return cm;
}

void setup() {
  Serial.begin(9600);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  pinMode(LED1_PIN, OUTPUT);
  pinMode(LED2_PIN, OUTPUT);

  digitalWrite(LED1_PIN, LOW);
  digitalWrite(LED2_PIN, LOW);

  gateServo.attach(SERVO_PIN);
  gateServo.write(CLOSE_ANGLE);

  Serial.println("System ready ✅");
}

void loop() {
  // ---- Read signal from PC (camera) ----
  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '1')      ownerDetected = true;   // owner detected by camera
    else if (c == '0') ownerDetected = false;  // no owner
  }

  long distance = readDistanceCM();

  // Debug print
  Serial.print("Distance: ");
  Serial.print(distance);
  Serial.print(" cm | Owner: ");
  Serial.println(ownerDetected ? "YES" : "NO");

  // --- LOGIC ---
  // Gate/LED ON only if owner detected AND object within 3 cm
  if (ownerDetected && distance <= THRESHOLD_CM) {
    gateServo.write(OPEN_ANGLE);   // open gate
    digitalWrite(LED1_PIN, HIGH);  // LEDs ON
    digitalWrite(LED2_PIN, HIGH);
  } else {
    gateServo.write(CLOSE_ANGLE);  // close gate
    digitalWrite(LED1_PIN, LOW);   // LEDs OFF
    digitalWrite(LED2_PIN, LOW);
  }

  delay(100); // small delay
}
