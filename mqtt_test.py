import time
import paho.mqtt.client as mqtt

MQTT_HOST = "broker.hivemq.com"
MQTT_BASE = "aiu/gate/aria"

client = mqtt.Client()
client.connect(MQTT_HOST, 1883, 60)
client.loop_start()

i = 0
while True:
    i += 1
    client.publish(f"{MQTT_BASE}/test", f"hello {i}")
    print("published", i)
    time.sleep(1)
