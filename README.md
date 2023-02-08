# FreakWAN and a MicroPython SX1276 driver

This repository is a work in progress for the following two projects that are going to live in the same place:

* An SX1276 driver written in MicroPython, for devices like the LYLIGO TTGO LoRa v2 1.6 and similar.
* A simple WAN system using LoRa devices, called FreakWAN, part of the [FreakNet](https://www.freaknet.org/) project.

The driver itself is already usable, and the `example.py` file shows how to work with it. Soon this README will be populated with all the documentation both for the driver and for the FreakWAN, but for now all is in its initial stage.

## Message formats

The low level (layer 2) format is the one with the explicit header selected, so it is up to the chip to add a length, a CRC and so forth. This layer is not covered here, as from the SX1276 driver we directly get the *clean* bytes received. So this covers layer 3, that is the messages format implemented by FreakWan.

The first byte is the message byte. The following message types are defined:

* MessageTypeData = 0
* MessageTypeACK = 1
* MessageTypeHello = 2
* MessageTypeBulkStart = 3
* MessageTypeBulkData = 4
* MessageTypeBulkEND = 5
* MessageTypeBulkReply = 6

However so far only data messages are implemented. This is the data message
format:

```
+-------------+--------------------+-----------+---------------+---------//
| 8 bits type | 32 bits message ID | 8 bit TTL | 48 bit sender | Message string
+-------------+--------------------+-----------+---------------+---------//
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
