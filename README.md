# lora_harness
This harness will work with meshtastic and with the leca device to generate messages and harvests stats.

## Setup
In the root folder of this project create a .env file with the following configurations
```
BROKER="your mqtt broker url"
PORT=1883
TOPIC_SNT="root/snt"
TOPIC_RCV="root/rcv"
```