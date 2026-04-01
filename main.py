import json
import os
import csv
import time
import random
import string
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import threading

load_dotenv()

# -------------------------------------------------------
# ENV CONFIG
# -------------------------------------------------------

SRC_ROOT = os.getenv("ROOT_SRC")
DST_ROOT = os.getenv("ROOT_DST")
SRC_NODE_ID_HEX = os.getenv("SRC_NODE_HEX")
CHANNEL = os.getenv("CHANNEL")
NODE_ID = os.getenv("NODE_ID")
BROKER = os.getenv("BROKER")

SRC_NODE_ID_INT = int(SRC_NODE_ID_HEX, 16)
PORT = int(os.getenv("PORT", 1883))
TOTAL_MESSAGES = int(os.getenv("TOTAL_MESSAGES", 10))
TARGET_SIZE = int(os.getenv("TARGET_SIZE", 50))
SLEEP_S = float(os.getenv("SLEEP_S", 1.0))

SRC_TOPIC = f"{SRC_ROOT}/2/json/mqtt/!{SRC_NODE_ID_HEX}"
DST_TOPIC = f"{DST_ROOT}/2/json/{CHANNEL}/+"

# -------------------------------------------------------
# DATA STRUCTURES
# -------------------------------------------------------

# sent_messages format: { msg_id: {"size": int, "sent_ts": float} }
sent_messages = {}

# received_messages format: { msg_id: { node_id: arrival_ts_float } }
received_messages = {}

lock = threading.Lock()

# -------------------------------------------------------
# MQTT CALLBACKS
# -------------------------------------------------------

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connected to broker with result code {rc}")
    print(f"Subscribing to {DST_TOPIC}")
    client.subscribe(DST_TOPIC)

def on_message(client, userdata, msg):
    try:

        arrival_time = time.time()
        topic_parts = msg.topic.split('/')
        node_id = topic_parts[-1]

        payload_str = msg.payload.decode()

        print("\n<<< RECEIVED MQTT MESSAGE")
        print("Topic:", msg.topic)
        print("Payload:", payload_str)

        data = json.loads(payload_str)

        full_text = data.get("payload", {}).get("text", "")

        if not full_text:
            return

        parts = full_text.split(",", 2)

        if len(parts) < 2:
            return

        msg_id = int(parts[0])
        size = parts[1]

        print(f"<<<<<< Parsed Message | msg_id={msg_id} | node={node_id} | size={size}")

        with lock:

            if msg_id not in received_messages:
                received_messages[msg_id] = {}

            if node_id not in received_messages[msg_id]:
                received_messages[msg_id][node_id] = arrival_time

                print(f"Saved arrival for msg {msg_id} from node {node_id}")

    except Exception as e:
        print("Error parsing message:", e)

# -------------------------------------------------------
# SENDER
# -------------------------------------------------------

def send_messages(client):

    print(f"\nStarting to send {TOTAL_MESSAGES} messages")

    for msg_id in range(1, TOTAL_MESSAGES + 1):

        prefix = f"{msg_id},{NODE_ID},"

        padding_needed = TARGET_SIZE - len(prefix)

        padding = ''.join(
            random.choices(string.ascii_letters, k=max(0, padding_needed))
        )

        harness_message = prefix + padding

        message_data = {
            "from": SRC_NODE_ID_INT,
            "channel": 0,
            "type": "sendtext",
            "payload": harness_message
        }

        json_payload = json.dumps(message_data)

        with lock:
            sent_messages[msg_id] = {
                "size": len(json_payload.encode()),
                "sent_ts": time.time()
            }

        client.publish(SRC_TOPIC, json_payload, qos=1)

        print(f">>>>>> SENT msg_id={msg_id}")

        time.sleep(SLEEP_S)

# -------------------------------------------------------
# RESULTS
# -------------------------------------------------------

def write_results():

    csv_filename = "mqtt_results.csv"

    with open(csv_filename, mode="w", newline="") as file:

        writer = csv.writer(file)

        writer.writerow([
            "msg_id",
            "size_bytes",
            "avg_delivery_time_s",
            "max_delivery_time_s",
            "min_delivery_time_s",
            "node_count"
        ])

        with lock:

            for msg_id, sent_info in sent_messages.items():

                size = sent_info["size"]
                sent_ts = sent_info["sent_ts"]

                receivers = received_messages.get(msg_id, {})
                node_count = len(receivers)

                if node_count > 0:

                    latencies = [
                        arrival_ts - sent_ts
                        for arrival_ts in receivers.values()
                    ]

                    min_time = min(latencies)
                    max_time = max(latencies)
                    avg_time = sum(latencies) / node_count

                else:

                    min_time = "Timeout/Lost"
                    max_time = "Timeout/Lost"
                    avg_time = "Timeout/Lost"

                writer.writerow([
                    msg_id,
                    size,
                    avg_time,
                    max_time,
                    min_time,
                    node_count
                ])

    print("\nResults written to:", csv_filename)

# -------------------------------------------------------
# MAIN
# -------------------------------------------------------

if __name__ == '__main__':
    print(f"Connecting to {BROKER} on port {PORT}...")

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    client.on_connect = on_connect

    client.connect(BROKER, PORT, 60)

    client.loop_start()

    # wait for subscriptions
    time.sleep(3)

    send_messages(client)

    print("\nAll messages sent, waiting for replies...")
    time.sleep(10)

    client.loop_stop()
    client.disconnect()

    write_results()