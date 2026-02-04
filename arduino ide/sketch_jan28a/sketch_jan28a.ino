#include <Servo.h>
Servo gateServo;

// ----- Pins -----
const int TRIG_PIN  = 10;
const int ECHO_PIN  = 11;
const int SERVO_PIN = 9;

const int LED1_PIN = 4;
const int LED2_PIN = 5;

const int PIR_PIN  = 7;   // ✅ PIR OUT -> D7

// ----- Settings -----
const int THRESHOLD_CM = 10;
const int OPEN_ANGLE   = 90;
const int CLOSE_ANGLE  = 0;

bool ownerDetected = false;   // from Python (O1/O0)
bool sessionActive = false;   // from Python (S1/S0)
bool gateOpen      = false;

long readDistanceCM() {
  digitalWrite(TRIG_PIN, LOW); delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return 999;
  return duration * 0.0343 / 2.0;
}

void setGate(bool open) {
  gateOpen = open;
  if (open) {
    gateServo.write(OPEN_ANGLE);
    digitalWrite(LED1_PIN, HIGH);
    digitalWrite(LED2_PIN, HIGH);
  } else {
    gateServo.write(CLOSE_ANGLE);
    digitalWrite(LED1_PIN, LOW);
    digitalWrite(LED2_PIN, LOW);
  }
}

void setup() {
  Serial.begin(9600);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  pinMode(LED1_PIN, OUTPUT);
  pinMode(LED2_PIN, OUTPUT);

  pinMode(PIR_PIN, INPUT);

  gateServo.attach(SERVO_PIN);
  setGate(false);
}

void loop() {
  // Read commands from Python: O1/O0 and S1/S0
  while (Serial.available() > 0) {
    char c = Serial.read();

    if (c == 'O') {               // Owner command
      while (!Serial.available()) {}
      char v = Serial.read();
      ownerDetected = (v == '1');
    }
    else if (c == 'S') {          // Session command
      while (!Serial.available()) {}
      char v = Serial.read();
      sessionActive = (v == '1');
    }
  }

  long distance = readDistanceCM();
  bool pirMotion = (digitalRead(PIR_PIN) == HIGH);

  // Gate logic: session + owner + distance
  if (sessionActive && ownerDetected && distance < THRESHOLD_CM) {
    setGate(true);
  } else {
    setGate(false);
  }

  // Send status to Python
  // DIST,12,PIR,1,SESSION,1,OWNER,1,GATE,1
  Serial.print("DIST,"); Serial.print(distance);
  Serial.print(",PIR,"); Serial.print(pirMotion ? 1 : 0);
  Serial.print(",SESSION,"); Serial.print(sessionActive ? 1 : 0);
  Serial.print(",OWNER,"); Serial.print(ownerDetected ? 1 : 0);
  Serial.print(",GATE,"); Serial.println(gateOpen ? 1 : 0);

  delay(150);
}
