# FreakWAN and a MicroPython SX1276 driver

This repository is a work in progress for the following two projects that are going to live in the same place:

* An SX1276 driver written in MicroPython, for devices like the LYLIGO TTGO LoRa (TM) v2 1.6 and similar.
* A simple WAN system using LoRa devices, called FreakWAN, part of the [FreakNet](https://en.wikipedia.org/wiki/FreakNet)project.

The driver itself is already usable, and the `example.py` file shows how to work with it, just copy it inside your project and you are done. The rest of this README is about FreakWAN, the project that uses this driver to create a distributed messaging system over LoRa.

# FreakWAN

FreakWAN is an effort to create a LoRa based, open WAN network over LoRa.
Our goal is to cover parts of the Sicily which such network. However the code
will be freely available for anyone wanting to build their own LoRa
WANs on top of this work.

This code is currently NOT COMPLETE and designed to work with the
LYLOGO TTGO ESP32 LoRa module.

# Installation

* Install [MicroPython](https://micropython.org/download/LILYGO_TTGO_LORA32/) on your device.
* Optional: edit `wan_config.py` if you want to set your nickname and status message. This file will later contain more configuration parameters that are currently hard-coded inside the code, since for now all is alpha stage.
* Transfer all the `.py` files in the root directory of this project (with the exception of `example.py`, that is not needed) in your device.
* Restart your device.

# Usage

It is possible to use the device via Bluetooth, using one of the following applications:
* Mobile: install one of the many BLE UART apps in your phone. For instance, if you use [nRF Toolbox](https://www.nordicsemi.com/Products/Development-tools/nrf-toolbox), select the UART utility service, connect to the device and send a text message or just `!help`. On Android, we recommend the [Serial Bluetooth Terminal app](https://play.google.com/store/apps/details?id=de.kai_morich.serial_bluetooth_terminal&hl=en&gl=US). It works great out of the box, but for the best experience go to Settings, *Send* tab, and select *clear input on send*.
* Desktup: install [Freakble](https://github.com/eriol/freakble) following the project README.

Using one of the above, you can talk with the device sending CLI commands.
If you just send some text, it will be sent as message in the network.
If you send a valid command starting with the `!` character, it will be executed. For now you can use:
* `!automsg` [on/off] to disable enable automatic messages used for testing.
* `!bat` to show the battery level.

## Message formats

The low level (layer 2) format is the one with the explicit header selected, so it is up to the chip to add a length, a CRC and so forth. This layer is not covered here, as from the SX1276 driver we directly get the *clean* bytes received. So this covers layer 3, that is the messages format implemented by FreakWan.

The first byte is the message byte. The following message types are defined:

* MessageTypeData = 0
* MessageTypeAck = 1
* MessageTypeHello = 2
* MessageTypeBulkStart = 3
* MessageTypeBulkData = 4
* MessageTypeBulkEND = 5
* MessageTypeBulkReply = 6

The second byte of messages of all the message types is the flag byte.
Bits have the following meaning:

* Bit 0: `Ralayed`. Set if the message was repeated by some node that is not the originator of the message. Relayed messages are not acknowledged.
* Bit 1: `PleaseRelay`. If this flag is set, other receivers of the message will try to repeat the message, so that it can travel further in the WAN.
* Bit 1-7: Reserved for future uses. Should be 0.

Currently not all the message types are implemented.

## DATA message

Format:

```
+--------+---------+---------------+-------+-----------+------------------//
| type:8 | flags:8 | message ID:32 | TTL:8 | sender:48 | Message string:...
+--------+---------+---------------+-------+-----------+------------------//
```

Note that there is no message length, as it is implicitly encoded in the
previous layer. The Message string is in the following format:

    nickname:message

The TTL is set to 255 normally, and decreased at every retransmission.
The sender ID is the HMAC returned by the device API, while the 32 bit
message ID is generated randomly, and is used in order to mark a message
as already processed, in order to discard duplicates (and there are many
since the protocol uses broadcasted retransmissions in order to build the WAN).

Note that on retransmissions of the same message by other nodes, with
the scope of reaaching the whole network, the message sender remains set
to the *same sender of the original message*, that is, the device that
created the message the first time. So there is no way to tell who
sent a given retransmission of a given message.

## ACK message

The ACK message is used to acknowledge the sender that some nearby device
actually received the message sent. ACKs are sent only when receiving
messages of type data, and only if the `Relayed` flag is not set. The idea
is that the originator of a message wants to understand if at least
*some* device received it, of the ones it is directly connected. The
message can be repeated multiple times and reach very far nodes, but
we don't want all those nodes to waste channel time sending ACKs: basically
in many cases we would waste more channel time by receiving ACKs to stop
retransmission than by just repeating the message N times, especially if
N is small and we have many neighbor nodes. More about this in the
messages relay section of this document.

Format:

```
+--------+---------+---------------+-----------------+---------------+
| type:8 | flags:8 | message ID:32 | 8 bits ack type | 46 bit sender |
+--------+---------+---------------+-----------------+---------------+
```

Where:
* The type id is MessageTypeAck
* Flags are set to 0. Ack messages should never be repeated.
* The 32 bit message ID is the ID of the acknowledged message. ACKs don't have a message ID for the ACK itself, as they are *fire and forget* and it would not be useful.
* The ACK type is the message type of the original message we are acknowledging.
* Sender is the sender node, the one that is acknowledging the message, so this is NOT the sender of the original massage. The sender field is used so that who sent the acknowledged message can know which node acknowledged it.

## HELLO message

This message has the unique goal of advertising our presence to other
devices in the network. This way, when a new device, part of the WAN,
is powered on, it can tell if it is alone or surrounded by one or more
other participants that are near enough to be received.

Hello messages are sent periodically, with a random period between
60000 and 120000 milliseconds (one to two minutes).

Devices receiving hello messages will compile a list of neighbors. A
device is removed from the list if we don't receive an hello message
from it for 10 minutes (this means we need to miss many successive
hello messages, in order to remove a device -- this is an important point
since we need to account for the high probability of losing messages
for being in TX mode while some other node broadcasts).

Format:

```
+--------+---------+---------------+--------+------------\\
| type:8 | flags:8 | 46 bit sender | seen:8 | status message
+--------+---------+---------------+--------+------------\\
```

* The type id is set to the hello message type.
* Flags are currently unused for the hello message.
* The sender is the device ID of the sender.
* Seen is the number of devices this device is currently sensing, that is, the length of its neighbors list.
* The status message is a string composed of the nickname of the owner, then a semicolon, and a message that the user can set. Like:

    antirez:Hi there! I'm part of FreakWAN.

# Messages relay

Data messages with the `PleaseRelay` flag set are retransmitted by the nodes receiving them. The retransmission is the fundamental way in which the WAN is built. Imagine the following FreakWAN set of devices:

    A <------ 10 km -------> B <----- 10km -----> C

For a message sent by A to reach C, if we imagine a range of, for instance,
12 km, When B receives the messages created by A it must repeat the messages, so that C can also receive them.

To do so, FreakWAN uses the following mechanism:

1. A data message that has the `PleaseRelay` bit set, when received gets retransmitted, assuming its TTL is still greater than 1. The TTL of the message is decremented by one, the `Relayed` flag is set in the message, finally the message is send again *as it is*, without changing the sender address, but maintaining the original one.
2. Devices may chose to avoid retransmitting messages with a too high RSSI, in order to avoid using precious channel time without a good reason. It is of little interest that two very nearby devices retransmit their messages.
3. Retransmitted messages have the `Relayed` flag set, so ACKs are not transmitted by the receivers of those messages. FreakWAN ACKs only serve to inform the originator of the message that some neighbor device received the message, but are not used in order to notify of the final destinations of the message, as this would require a lot of channel time and is quite useless: for direct messages, that can be created on top of the public ones, it is possible for the receiver to send back an explicit acknowledge of some kind.
4. Each message received and never seen before is relayed N times, with N being a configuration inside the program defaulting to 3. However users may change it, depending on the network nodes density and other parameters.
