import json
import os
import csv
import time
import random
import string
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

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

# sent_messages format: { msg_id: {"size": int, "sent_ts": float} }
sent_messages = {}

# received_messages format: { msg_id: { node_id: arrival_ts_float } }
received_messages = {}

def on_message(client, userdata, msg):
    try:
        arrival_time = time.time()
        topic_parts = msg.topic.split('/')
        node_id = topic_parts[-1]

        data = json.loads(msg.payload.decode())
        full_text = data.get("payload", {}).get("text", "")
        parts = full_text.split(',', 2)

        if len(parts) >= 2:
            msg_id = int(parts[0])
            size = parts[1]

            print(f"<<<<<< Message Received | Sender (Topic): {node_id} | Msg ID: {msg_id} | Size: {size}")
            if msg_id not in received_messages:
                received_messages[msg_id] = {}

            if node_id not in received_messages[msg_id]:
                received_messages[msg_id][node_id] = arrival_time
                print(f"       -> Saved reply for msg_id: {msg_id} from node_id: {node_id}")

    except ValueError:
        print(f"Error: Could not convert msgid to integer. Payload: {full_text}")
    except Exception as e:
        print(f"Error parsing message: {e}")


if __name__ == '__main__':
    print(f"Connecting to {BROKER} on port {PORT}...")

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)

    client.loop_start()

    print(f"Subscribing to to {DST_TOPIC}")
    client.subscribe(DST_TOPIC)

    time.sleep(5)

    print(f"Starting to send {TOTAL_MESSAGES} messages...")
    for msg_id in range(1, TOTAL_MESSAGES + 1):
        prefix = f"{msg_id},{NODE_ID},"
        padding_needed = TARGET_SIZE - len(prefix)
        padding = ''.join(random.choices(string.ascii_letters, k=padding_needed)) if padding_needed > 0 else ""
        harness_message = prefix + padding

        message_data = {
            "from": SRC_NODE_ID_INT,
            "channel": 0,
            "type": "sendtext",
            "payload": harness_message
        }
        json_payload = json.dumps(message_data)

        sent_messages[msg_id] = {
            "size": len(json_payload.encode('utf-8')),
            "sent_ts": time.time()
        }

        result = client.publish(SRC_TOPIC, json_payload, qos=1)
        result.wait_for_publish()

        print(f">>>>>> Message '{harness_message}' sent to topic '{SRC_TOPIC}'")

        time.sleep(SLEEP_S)
    try:
        print("All messages sent! Waiting for replies...")
        time.sleep(5)
    except KeyboardInterrupt:
        print("\nStopping experiment and computing results...")

    client.loop_stop()
    client.disconnect()

    csv_filename = "mqtt_results.csv"

    with open(csv_filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        # Write Headers
        writer.writerow(
            ["msg_id", "size_bytes", "avg_delivery_time_s", "max_delivery_time_s", "min_delivery_time_s", "node_count"])

        for msg_id, sent_info in sent_messages.items():
            size = sent_info["size"]
            sent_ts = sent_info["sent_ts"]

            # Get all the nodes that replied to this msg_id
            receivers = received_messages.get(msg_id, {})
            node_count = len(receivers)

            if node_count > 0:
                # Calculate latency for each node that received this message
                latencies = [(arrival_ts - sent_ts) for arrival_ts in receivers.values()]

                min_time = min(latencies)
                max_time = max(latencies)
                avg_time = sum(latencies) / node_count
            else:
                # No nodes received this message
                min_time = max_time = avg_time = "Timeout/Lost"

            writer.writerow([msg_id, size, avg_time, max_time, min_time, node_count])

    print(f"Results successfully saved to {csv_filename}!")