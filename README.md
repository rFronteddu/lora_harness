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
In the root folder of this project create a .env file with the following configurations
* BROKER: Your mqtt broker ex: mqtt.xxx.us
* PORT: Your mqtt port ex: 1883
* ROOT_SRC: Publisher will get messages from here
* ROOT_DST: Receivers will push messages here, MUST BE DIFFERENT FROM ROOT_SRC
* SRC_NODE_HEX: Hex ID of the publisher node (do not include the !).
* CHANNEL: Name of the channel configuration actually used by the nodes (I think default channel is 0 and that's why messages are sent to that channel)
* TOTAL_MESSAGES: How many messages to send
* TARGET_SIZE= Target size of the payload (note that each protocol may add more data)
* NODE_ID: Id of the publisher
* SLEEP_S: Seconds between messages

```
BROKER=
PORT=1883
ROOT_SRC=msh/EU
ROOT_DST=msh/EU_SNT
SRC_NODE_HEX=6982912c
CHANNEL=ShortTurbo
TOTAL_MESSAGES=100
TARGET_SIZE=64
NODE_ID=101
SLEEP_S=5
```

### Meshtastic
Meshtastic firmware is very unstable, I configured things in the following order
* Setup all lora configurations
* setup the mqtt channel in all nodes
  * configure publisher downlink from mqtt channel
  * configured receivers primary channel to uplink
* enable wifi
* enable mqtt connection


