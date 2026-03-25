import os
import csv
import time
import random
import string
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

# sent_messages format: { msg_id: {"size": int, "sent_ts": float} }
sent_messages = {}

# received_messages format: { msg_id: { node_id: arrival_ts_float } }
received_messages = {}

def on_message(client, userdata, message):
    try:
        payload = message.payload.decode("utf-8")
        arrival_time = time.time()

        # Split the string: "msg_id,node_id,padding..."
        parts = payload.split(',', 2)  # Split only on the first two commas

        if len(parts) >= 3:
            msg_id = int(parts[0])
            node_id = int(parts[1])

            # Initialize the nested dict for this msg_id if it doesn't exist
            if msg_id not in received_messages:
                received_messages[msg_id] = {}

                # KEEP OLDER: Only save if we haven't seen this node reply to this msg_id yet
                if node_id not in received_messages[msg_id]:
                    received_messages[msg_id][node_id] = arrival_time
                    print(f"Received msg_id: {msg_id} from node_id: {node_id}")

    except Exception as e:
        print(f"Error parsing message: {e}")

if __name__ == '__main__':
    broker = os.getenv("BROKER")
    port = int(os.getenv("PORT"))  # Convert to integer for MQTT clients
    topic_snt = os.getenv("TOPIC_SNT")
    topic_rcv = os.getenv("TOPIC_RCV")

    TOTAL_MESSAGES = 100
    TARGET_SIZE = 64
    NODE_ID = 101
    SLEEP_S = 1

    print(f"Connecting to {broker} on port {port}...")

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    client.connect(broker, port, 60)

    client.loop_start()
    client.subscribe(topic_rcv)

    time.sleep(1)

    print(f"Starting to send {TOTAL_MESSAGES} messages...")
    for msg_id in range(1, TOTAL_MESSAGES + 1):
        prefix = f"{msg_id},{NODE_ID},"
        padding_needed = TARGET_SIZE - len(prefix)
        padding = ''.join(random.choices(string.ascii_letters, k=padding_needed)) if padding_needed > 0 else ""
        payload = prefix + padding

        sent_messages[msg_id] = {
            "size": len(payload.encode('utf-8')),
            "sent_ts": time.time()
        }

        result = client.publish(topic_snt, payload, qos=1)
        result.wait_for_publish()

        print(f"Message '{payload}' sent to topic '{topic_snt}'")

        time.sleep(SLEEP_S)

    try:
        print("All messages sent! Waiting for replies...")
        print("Press Ctrl+C when you are ready to stop the experiment and generate the CSV.")
        while True:
            time.sleep(1)  # Keeps main thread alive while background thread listens
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
            min_time = max_time = avg_time = None

        writer.writerow([msg_id, size, avg_time, max_time, min_time, node_count])

print(f"Results successfully saved to {csv_filename}!")