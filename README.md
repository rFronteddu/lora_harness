# lora_harness
README UNDER CONSTRUCTION

LoRa Harness
A testing and benchmarking utility for generating messages and harvesting 
performance statistics across multiple LoRa and networking protocols, 
including [Meshtastic](https://meshtastic.org/), [Meshcore](https://meshcore.co.uk/), and LRF (IHMC Radio Framework).

## Architecture Overview
The harness operates in three primary modes: Harness (orchestrator), 
Sender, and Receiver. It utilizes an MQTT broker as the central message 
bus to coordinate between these distributed components.

```mermaid
flowchart TD
    A[Program Start] --> B[Load .env configuration]
    B --> C[Initialize MQTT Client]
    C --> D[Connect to Broker]
    D --> E[MQTT loop_start]
    E --> F{MODE?}

    %% Harness Mode
    F -->|harness| H1["send_messages()<br>Generate harness message"]
    H1 --> H2[Create msg_id, NODE_ID, padding]
    H2 --> H3{PROTOCOL?}
    H3 -->|meshtastic| H4["Publish JSON to<br>MESHTASTIC MQTT topic"]
    H3 -->|lrf/meshcore| H5["Publish message<br>to Protocol MQTT topic"]
    H4 --> H6["Store sent_messages[msg_id]"]
    H5 --> H6
    H6 --> H7[Wait for responses]
    H7 --> H8["process_message()"]
    H8 --> H9["save_receive_stat()"]
    H9 --> H10["write_results() → CSV files"]

    %% Sender Mode
    F -->|sender| S1[Subscribe to LRF sender topic]
    S1 --> S2["MQTT on_message()"]
    S2 --> S3["process_message()"]
    S3 --> S4{PROTOCOL?}
    S4 -->|lrf| S5["send_lrf_multicast()"]
    S5 --> S6[UDP Multicast Packet]

    %% Receiver Mode
    F -->|receiver| R1["lrf_receive()"]
    R1 --> R2[Listen UDP multicast socket]
    R2 --> R3[Receive multicast packet]
    R3 --> R4[Parse harness message]
    R4 --> R5[Create stat JSON]
    R5 --> R6[Publish stat to MQTT topic]

    %% Meshtastic Receive Path
    MQTT[(MQTT Broker)]
    MQTT --> M1["on_message()"]
    M1 --> M2["process_message()"]
    M2 --> M3[Parse Meshtastic JSON payload]
    M3 --> M4["save_receive_stat()"]

    %% Network
    S6 --> NET[(LRF LoRa Network)]
    NET --> R2
```

## Configuration (.env)
Configure the project by creating a .env file in the root directory.

| Variable       | Description                                |
|----------------|--------------------------------------------|
| BROKER         | "MQTT Broker address (e.g., mqtt.ihmc.us)" |
| NODE_ID        | Unique identifier for the current node     |
| SLEEP_S        | Delay between messages in seconds          |
| TOTAL_MESSAGES | Number of messages to send per test run    |
| TARGET_SIZE    | Desired payload size in bytes              |
| PROTOCOL       | "meshtastic, meshcore, or lrf"             |
| MODE           | "harness, sender, or receiver"             |

### Protocol Specifics
* Overhead: The harness does not automatically accounts for overhead added by protocols.

#### Meshtastic
* Topic Structure: Uses msh/EU for sending and msh/EU_SNT for receiving.
* Node ID: Requires MESHTASTIC_NODE_HEX (e.g., 6982912c).
* Notes: JSON output must be enabled in firmware.

#### Meshcore
* Bridge Support: Designed for the meshcore-mqtt bridge.
* Constraint: Use underscores in topics (e.g., meshcore_a) as hierarchical slashes may fail with certain bridge versions.

#### LRF (Custom)
* Used for Ethernet-based simulation/testing via UDP Multicast.
* Group: 224.0.0.1 | Port: 12345


## Setup
### Meshtastic Firmware (v2.7.15)
* To ensure stability during high-throughput testing:
  * Configure LoRa settings and frequency (863MHz).
  * Set Modem Preset to Short Turbo.
  * Set Max Transmit Power to 10dBm.
  * Important: Enable "Duty Cycle Override" and disable encryption to maximize testing transparency.
  * Enable WiFi and MQTT; ensure JSON Output is toggled ON.

### Meshcore (Firmware v1.14.1 - USB Companion)
* Configure nodes via the Meshcore WebApp.
* Trigger "Adv" (Advertisement) from all nodes prior to starting the harness to ensure routing tables are populated.
* MQTT Companion does not fully support hierarchical protocols, that's why we used _a, _b, _c, _d.