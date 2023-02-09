# FreakWAN and a MicroPython SX1276 driver

This repository is a work in progress for the following two projects that are going to live in the same place:

* An SX1276 driver written in MicroPython, for devices like the LYLIGO TTGO LoRa v2 1.6 and similar.
* A simple WAN system using LoRa devices, called FreakWAN, part of the [FreakNet](https://www.freaknet.org/) project.

The driver itself is already usable, and the `example.py` file shows how to work with it. Soon this README will be populated with all the documentation both for the driver and for the FreakWAN, but for now all is in its initial stage.

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

* Bit 0: Repeat. Set if the message was repeated by some node that is not the originator of the message. Repeat messages are not acknowledged.
* Bit 1-7: Reserved for future uses. Should be 0.

Currently not all the message types are implemented.

## Data message

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

## Ack message

The Ack message is used to acknowledge the sender that some nearby device
actually received the message sent. Acks are sent only when receiving
messages of type data, and only if the `repeat` flag is not set. The idea
is that the originator of a message wants to understand if at least
*some* device received it, of the ones it is directly connected. The the
message can be repeated multiple times and reach very far nodes, but
we don't want all those nodes to waste channel time sending Acks.

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

## Hello message

This message has the unique goal of advertising our presence to other
devices in the network. This way, when a new device, part of the WAN,
is powered on, it can tell if it is alone or surrounded by one or more
other participants that are near enough to be received.

Hello messages are sent periodically, with a random period between
60000 and 120000 milliseconds (one to two minutes).

Devices receiving hello messages will compile a list of neighbors. A
device is removed from the list if we don't receive an hello message
fro it for 5 minutes (this means we need to miss at least two successive
hello messages, in order to remove a device).

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


