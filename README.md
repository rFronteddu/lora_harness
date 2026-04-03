# lora_harness
This harness will work with meshtastic and with other LoRa based firmware to generate messages and harvests stats.

```mermaid
flowchart TD

%% -------------------------
%% Program Start
%% -------------------------
A[Program Start] --> B[Load .env configuration]
B --> C[Initialize MQTT Client]
C --> D[Connect to Broker]
D --> E[MQTT loop_start]
E --> F{MODE?}

%% -------------------------
%% Harness Mode
%% -------------------------
F -->|harness| H1["send_messages()<br>Generate harness message"]
H1 --> H2[Create msg_id, NODE_ID, padding]
H2 --> H3{PROTOCOL?}
H3 -->|meshtastic| H4["Publish JSON to<br>MESHTASTIC MQTT topic"]
H3 -->|lrf| H5["Publish raw harness message<br>to LRF MQTT topic"]
H4 --> H6["Store sent_messages[msg_id]"]
H5 --> H6
H6 --> H7[Wait for responses]
H7 --> H8["process_message()"]
H8 --> H9["save_receive_stat()"]
H9 --> H10["write_results() → CSV files"]

%% -------------------------
%% Sender Mode
%% -------------------------
F -->|sender| S1[Subscribe to LRF sender topic]
S1 --> S2["MQTT on_message()"]
S2 --> S3["process_message()"]
S3 --> S4{PROTOCOL?}
S4 -->|lrf| S5["send_lrf_multicast()"]
S5 --> S6[UDP Multicast Packet]

%% -------------------------
%% Receiver Mode
%% -------------------------
F -->|receiver| R1["lrf_receive()"]
R1 --> R2[Listen UDP multicast socket]
R2 --> R3[Receive multicast packet]
R3 --> R4[Parse harness message]
R4 --> R5[Create stat JSON]
R5 --> R6[Publish stat to MQTT topic]

%% -------------------------
%% Meshtastic Receive Path
%% -------------------------
MQTT[(MQTT Broker)]
MQTT --> M1["on_message()"]
M1 --> M2["process_message()"]
M2 --> M3[Parse Meshtastic JSON payload]
M3 --> M4["save_receive_stat()"]

%% -------------------------
%% Multicast Network
%% -------------------------
S6 --> NET[(LRF Multicast Network)]
NET --> R2
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


