import json
import os
import csv
import socket
import struct
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

MODE = os.getenv("MODE", "harness")  # harness | sender | receiver
PROTOCOL = os.getenv("PROTOCOL", "meshtastic")  # meshtastic | lrf
NODE_ID = os.getenv("NODE_ID")
BROKER = os.getenv("BROKER")
PORT = int(os.getenv("PORT", 1883))
TOTAL_MESSAGES = int(os.getenv("TOTAL_MESSAGES", 10))
TARGET_SIZE = int(os.getenv("TARGET_SIZE", 50))
SLEEP_S = float(os.getenv("SLEEP_S", 1.0))

# -------------------------------------------------------
# DATA STRUCTURES
# -------------------------------------------------------

sent_messages = {}  # { msg_id: {"size": int, "sent_ts": float} }
received_messages = {}  # { msg_id: { node_id: arrival_ts_float } }
arrival_logs = []  # raw arrival entries
lock = threading.Lock()

def save_receive_stat(msg_id, sender_id, rcvr_id, msg_size, arrival_time):
    """Store received message stats in global structures"""
    with lock:
        if msg_id not in received_messages:
            received_messages[msg_id] = {}
        if rcvr_id not in received_messages[msg_id]:
            received_messages[msg_id][rcvr_id] = arrival_time
            sent_time = sent_messages.get(msg_id, {}).get("sent_ts", None)
            arrival_logs.append({
                "sender_id": sender_id,
                "msg_id": msg_id,
                "size": msg_size,
                "rcvr_id": rcvr_id,
                "sent_time": sent_time,
                "arrival_time": arrival_time
            })

def process_message(msg):
    """Unified processing for Meshtastic and LRF messages"""
    arrival_time = time.perf_counter()

    try:
        # ---------------- MESHTASTIC ----------------
        if PROTOCOL == "meshtastic":
            payload_str = msg.payload.decode()
            topic_parts = msg.topic.split('/')
            rcvr_id = topic_parts[-1]
            data = json.loads(payload_str)
            full_text = data.get("payload", {}).get("text", "")
            if data.get("type") != "text" or not full_text:
                return

            parts = full_text.split(",", 2)
            if len(parts) < 2:
                return

            msg_id = int(parts[0])
            sender_id = parts[1]
            msg_size = len(full_text.encode())

        # ---------------- LRF ----------------
        elif PROTOCOL == "lrf":
            payload = msg.decode().strip() if isinstance(msg, bytes) else msg.payload.decode().strip()
            print("Received:", payload)

            # If this node is the sender bridge, forward to multicast
            if MODE == "sender":
                send_lrf_multicast(payload)
                return

            data = json.loads(payload)
            msg_id = int(data["msg_id"])
            sender_id = data["sender_id"]
            rcvr_id = data["receiver_id"]
            msg_size = int(data["size"])

        elif PROTOCOL == "meshcore":
            payload_str = msg.payload.decode()
            topic_parts = msg.topic.split('/')
            # Topic: meshcore_a/message/channel/0 -> rcvr_id is 'a'
            rcvr_id = topic_parts[0].split('_')[1]

            data = json.loads(payload_str)

            # Extract the nested text field
            full_text = data.get("payload", {}).get("text", "")
            if not full_text:
                print("No full text")
                return

            parts = full_text.split(",", 2)
            if len(parts) < 2:
                print("No len")
                return
            if ": " in full_text:
                # Splitting on ": " once gives us ["NodeA", "3,100,yahb..."]
                _, actual_csv_data = full_text.split(": ", 1)
            else:
                actual_csv_data = full_text

            parts = actual_csv_data.split(",", 2)
            if len(parts) < 2:
                return

            msg_id = int(parts[0])  # Should be 3
            sender_id = parts[1]  # Should be 100
            msg_size = len(full_text.encode())
        # ---------------- SAVE STATS ----------------
        save_receive_stat(msg_id, sender_id, rcvr_id, msg_size, arrival_time)
        print(f"[{PROTOCOL}] msg={msg_id} sender={sender_id} rcvr={rcvr_id} size={msg_size}")

    except Exception as e:
        print("Error processing message:", e)


# -------------------------------------------------------
# LRF MULTICAST SENDER
# -------------------------------------------------------

def send_lrf_multicast(payload_str):
    """Send LRF message via multicast"""
    group = os.getenv("LRF_MCAST_GROUP")
    port = int(os.getenv("LRF_MCAST_PORT"))
    iface = os.getenv("LRF_MCAST_IFACE")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(iface))
    sock.sendto(payload_str.encode(), (group, port))
    sock.close()
    print(f"Multicast sent -> {group}:{port}")


# -------------------------------------------------------
# MQTT CALLBACKS
# -------------------------------------------------------

def on_connect(client, userdata, flags, rc, properties=None):
    """Control MQTT subscriptions"""
    print(f"Connected to broker with result code {rc}")

    if PROTOCOL == "meshtastic":
        client.subscribe(f"{os.getenv('MESHTASTIC_RCV_TOPIC_ROOT')}/2/json/{os.getenv('MESHTASTIC_CHANNEL')}/+")
    elif PROTOCOL == "lrf":
        if MODE == "harness":
            client.subscribe(f"{os.getenv('LRF_RCV_TOPIC_ROOT')}/+")
        elif MODE == "sender":
            client.subscribe(f"{os.getenv('LRF_SNT_TOPIC_ROOT')}/{NODE_ID}")
    elif PROTOCOL == "meshcore":
        topics = [(os.getenv('MESHCORE_RCV_TOPIC_ROOT_1'), 0),
                  (os.getenv('MESHCORE_RCV_TOPIC_ROOT_2'), 0),
                  (os.getenv('MESHCORE_RCV_TOPIC_ROOT_3'), 0)]

        # topics = [("home/livingroom/temp", 0), ("home/kitchen/temp", 1)]
        client.subscribe(topics)

def on_message(client, userdata, msg):
    process_message(msg)

# -------------------------------------------------------
# SENDER
# -------------------------------------------------------

def send_messages(client):
    print(f"\nSending {TOTAL_MESSAGES} messages")

    for msg_id in range(1, TOTAL_MESSAGES + 1):
        prefix = f"{msg_id},{NODE_ID},"
        padding_needed = TARGET_SIZE - len(prefix)
        padding = ''.join(random.choices(string.ascii_letters, k=max(0, padding_needed)))
        harness_message = prefix + padding

        if PROTOCOL == "meshtastic":
            src_node_id_hex = os.getenv("MESHTASTIC_NODE_HEX")
            src_node_int = int(src_node_id_hex, 16)
            message_data = {"from": src_node_int, "channel": 0, "type": "sendtext", "payload": harness_message}
            json_payload = json.dumps(message_data)
            topic = f"{os.getenv('MESHTASTIC_SNT_TOPIC_ROOT')}/2/json/mqtt/!{src_node_id_hex}"
            client.publish(topic, json_payload, qos=1)
        elif PROTOCOL == "meshcore":
            topic = f"{os.getenv('MESHCORE_SNT_TOPIC_ROOT')}/command/send_chan_msg"
            message_data = {"channel": 0, "message": harness_message}
            json_payload = json.dumps(message_data)
            client.publish(topic, json_payload, qos=1)
        elif PROTOCOL == "lrf":
            topic = f"{os.getenv('LRF_SNT_TOPIC_ROOT')}/{NODE_ID}"
            client.publish(topic, harness_message, qos=1)

        with lock:
            sent_messages[msg_id] = {"size": len(harness_message), "sent_ts": time.perf_counter()}

        print(f">>>>>> SCHEDULED msg_id={msg_id}")
        time.sleep(SLEEP_S)

# -------------------------------------------------------
# RESULTS
# -------------------------------------------------------

def write_results():
    aggregate_csv_filename = os.getenv("FILE_ROOT") + "_summary.csv"
    details_csv_filename = os.getenv("FILE_ROOT") + ".csv"

    with open(aggregate_csv_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["msg_id", "size_bytes", "avg_delivery_time_s", "max_delivery_time_s", "min_delivery_time_s", "node_count"])

        with lock:
            for msg_id, sent_info in sent_messages.items():
                size = sent_info["size"]
                sent_ts = sent_info["sent_ts"]

                receivers = received_messages.get(msg_id, {})
                node_count = len(receivers)

                if node_count > 0:
                    latencies = [arrival_ts - sent_ts for arrival_ts in receivers.values()]

                    min_time = min(latencies)
                    max_time = max(latencies)
                    avg_time = sum(latencies) / node_count
                else:
                    min_time = max_time = avg_time = "Timeout/Lost"

                writer.writerow([msg_id, size, avg_time, max_time, min_time, node_count])
    print("\nAggregate results written to:", aggregate_csv_filename)

    with open(details_csv_filename, mode="w", newline="") as details_file:
        details_writer = csv.writer(details_file)

        details_writer.writerow(["sender_id", "msg_id", "size", "receiver_id", "generation_time", "arrival_time"])

        with lock:
            for entry in arrival_logs:
                details_writer.writerow([entry["sender_id"], entry["msg_id"], entry["size"], entry["rcvr_id"], entry["sent_time"], entry["arrival_time"]])

    print("Detailed arrival entries written to:", details_csv_filename)

# -------------------------------------------------------
# LRF RECEIVER (MULTICAST)
# -------------------------------------------------------

def lrf_receive():
    """Listen for multicast messages and publish stats to MQTT"""
    group = os.getenv("LRF_MCAST_GROUP")
    port = int(os.getenv("LRF_MCAST_PORT"))
    iface = os.getenv("LRF_MCAST_IFACE")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", port))
    mreq = struct.pack("4s4s", socket.inet_aton(group), socket.inet_aton(iface))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    print(f"Listening multicast {group}:{port}")

    receiver_id = NODE_ID
    receive_topic = f"{os.getenv('LRF_RCV_TOPIC_ROOT')}/{receiver_id}"

    while True:
        data, addr = sock.recvfrom(65535)
        arrival_time = time.perf_counter()
        try:
            payload_str = data.decode()
            parts = payload_str.split(",", 2)
            if len(parts) < 2:
                continue

            msg_id = int(parts[0])
            sender_id = parts[1]
            stat = {"sender_id": sender_id, "msg_id": msg_id, "receiver_id": receiver_id, "arrival_time": arrival_time, "size": len(data)}

            mqtt_client.publish(receive_topic, json.dumps(stat), qos=1)
            print(f"Received multicast msg {msg_id}")
        except Exception as e:
            print("Error processing multicast:", e)

# -------------------------------------------------------
# MAIN
# -------------------------------------------------------

if __name__ == '__main__':
    print(f"MODE = {MODE}, PROTOCOL = {PROTOCOL}")
    print(f"Connecting to {BROKER}:{PORT}...")

    mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.on_message = on_message
    mqtt_client.on_connect = on_connect
    mqtt_client.connect(BROKER, PORT, 60)
    mqtt_client.loop_start()
    time.sleep(3) # wait for subscriptions

    if MODE == "harness":
        send_messages(mqtt_client)
        print("Waiting for responses...")
        time.sleep(5)
        write_results()
    elif MODE == "sender":
        print(f"{MODE} running... press Ctrl+C to exit")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    elif MODE == "receiver":
        print("Receiver running... press Ctrl+C to exit")
        try:
            lrf_receive()
        except KeyboardInterrupt:
            pass

    mqtt_client.loop_stop()
    mqtt_client.disconnect()