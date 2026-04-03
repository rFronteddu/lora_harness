# lora_harness
This harness will work with meshtastic and with other LoRa based firmware to generate messages and harvests stats.

```mermaid
sequenceDiagram
    participant H as Python Harness (Sender)
    participant B as MQTT Broker
    participant M as Meshtastic Mesh (Nodes)
    participant R as Python Harness (Receiver)
    participant CSV as CSV Writer

    Note over H: Loop from 1 to TOTAL_MESSAGES

    H->>H: Generate msg_id & padding
    H->>H: sent_messages[msg_id] = time.time()

    H->>B: Publish to SRC_TOPIC (JSON)
    B->>M: Forward to Mesh Gateway

    Note over M: LoRa transmission

    M-->>B: Node replies (JSON)

    B->>R: Message received (on_message)
    R->>R: arrival_time = time.time()
    R->>R: Extract msg_id & node_id

    alt msg_id exists in sent_messages
        R->>R: Store arrival_time in received_messages
        Note right of R: Latency = arrival - sent
    end

    Note over R: Wait 5 seconds

    R->>CSV: Calculate stats (min/max/avg)
    CSV-->>R: mqtt_results.csv
```

## Setup
### Project

```
# GENERAL
BROKER=
PORT=1883
NODE_ID=101
SLEEP_S=5
TOTAL_MESSAGES=10
TARGET_SIZE=64

# PROTOCOL=lrf
PROTOCOL=meshtastic

MODE=harness
# MODE=sender
# MODE=receiver

# -------------------------------------------------------
# MESHTASTIC
# -------------------------------------------------------
# meshtastic looks for messages to send in MESHTASTIC_SNT_TOPIC_ROOT/2/json/mqtt/!NODE_ID_HEX
MESHTASTIC_SNT_TOPIC_ROOT=msh/EU
# nodes will publish received messages here
MESHTASTIC_RCV_TOPIC_ROOT=msh/EU_SNT
MESHTASTIC_NODE_HEX=6982912c
MESHTASTIC_CHANNEL=ShortFast

# -------------------------------------------------------
# LRF
# -------------------------------------------------------
LRF_MCAST_GROUP=224.0.0.1
LRF_MCAST_PORT=12345
LRF_MCAST_IFACE=192.168.1.10

# the sender will send messages received from LRF_SNT_TOPIC_ROOT/NODE_ID
LRF_SNT_TOPIC_ROOT=lrf/SEND
# nodes will receive messages from here
LRF_RCV_TOPIC_ROOT=lrf/RCV
```

### Meshtastic
Meshtastic firmware is very unstable, I configured things in the following order
* Setup all lora configurations
* setup the mqtt channel in all nodes
  * configure publisher downlink from mqtt channel
  * configured receivers primary channel to uplink
* enable wifi
* enable mqtt connection


