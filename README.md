# FreakWAN and a MicroPython SX1276 driver

This repository is a work in progress for the following two projects that are going to live in the same place:

* An SX1276 driver written in MicroPython, for devices like the LILYGO TTGO LoRa (TM) v2 1.6 and similar.
* A simple WAN system using LoRa devices, called FreakWAN, part of the [FreakNet](https://en.wikipedia.org/wiki/FreakNet)project.
* A protocol specification, the one used in the implementation of FreakWAN, to be used upon the LoRa physical layer in order to build a system capable of supporting a chat between distributed users, where intermediate devices relay messages in order to build a mesh able to cover a wide area.

The driver itself is the single file `sx1276.py`, and the `example.py` file shows how to work with it: just copy the driver inside your project and you are done. The rest of this README is about FreakWAN, the project that uses this driver to create a distributed messaging system over LoRa.

# FreakWAN

FreakWAN is an effort to create a LoRa-based open WAN network over LoRa.
Our goal is to cover parts of the Sicily which such network. However the code
will be freely available for anyone wanting to build their own LoRa
WANs on top of this work.

This code is currently yet not complete, and designed to work with the
following ESP32-based devices:

1. LILYGO TTGO T3 v2 1.6 LoRa module.
2. LILYGO TTGO T Beam LoRa module.

However changing the pins setup to adapt it to other ESP32 modules that have an SX1276 (or compatible) LoRa chip and an SSD1306 display, should be very little work.

# Installation

* Install [MicroPython](https://micropython.org/download/LILYGO_TTGO_LORA32/) on your device.
* Optional: edit `wan_config.py` if you want to set your nickname and status message, set the frequency according to your device, and so forth. **Warning**: make sure to set the right frequency based on the LoRa module you own, and make sure your antenna is already installed before using the software, or you may damage your hardware.
* Transfer all the `.py` files in the root directory of this project (with the exception of `example.py`, that is not needed -- however also transferring it will do no harm) in your device. To transfer the files, you can use [ampy](https://github.com/scientifichackers/ampy) (`pip3 install adafruit-ampy` should be enough), or an alternative tool that we wrote and is conceptually part of the FreakWAN effort, called [talk32](https://github.com/antirez/talk32). Talk32 is much faster at transferring files, but is yet alpha quality code.
* Restart your device.

# Usage

It is possible to use the device via Bluetooth, using one of the following applications:
* Mobile: install one of the many BLE UART apps in your phone. For instance, if you use [nRF Toolbox](https://www.nordicsemi.com/Products/Development-tools/nrf-toolbox), select the UART utility service, connect to the device and send a text message or just `!help`. On Android, we recommend the [Serial Bluetooth Terminal app](https://play.google.com/store/apps/details?id=de.kai_morich.serial_bluetooth_terminal&hl=en&gl=US). It works great out of the box, but for the best experience go to Settings, *Send* tab, and select *clear input on send*.
* Desktop: install [Freakble](https://github.com/eriol/freakble) following the project README.

Using one of the above, you can talk with the device sending CLI commands.
If you just send some text, it will be sent as message in the network.
If you send a valid command starting with the `!` character, it will be executed. For now you can use:
* `!automsg` [on/off] to disable enable automatic messages used for testing.
* `!bat` to show the battery level.
* `!preset <name>` to set a LoRa preset. Each preset is a specific spreading, bandiwidth and coding rate setup. To see all the available presets write `!preset help`.
* `!sp`, `!bw`, `!cr` change the spreading, bandwidth and coding rate independently, if you wish.
* `!ls` shows the list of nodes this node is sensing via HELLO messages.
* `!font big|small` will change between an 8x8 and a 5x7 (4x6 usable area) font.
* `!image <image-file-name>` send an FCI image (see later about images).

## Sending images

FreakWAN implements its own very small, losslessy compressed 1 bit images, as a proof of concept that we can send small media types over LoRa, and also very useful in order to make our protocol more robust against very long packets (that have a very large *time on air*). Inside the `fci` directory of this repository you will find the specification of the image format and run length compression used, and a tool to convert small PNG files into FCI images.

Once you have the FCI images, you should copy them into the `images` directory inside your device (again, using ampy or talk32 or any other tool). Then you can send the images using the `!image` command using the bluetooth CLI.

## Power management

Right now, for the LILYGO TTGO T3 device, we support reading the battery level and shutting down the device when the battery is too low, since the battery could damage if it is discharged over a certain limit. When this happens, the device will go in deep sleep mode, and will flash the led 3 times every 5 seconds. Then, once connected again to the charger, when the battery charges a bit, it will restart again.

For the T Beam, work is in progress to provide the same feature. For now it is better to disable the power management at all, by setting `config['sleep_battery_perc']` to 0 in the `wan_config.py` file.

# FreakWAN network specification

The rest of this document is useful for anybody wanting to understand the internals of FreakWAN. The kind of messages it sends, how messages are relayed in order to reach far nodes, the retransmission and acknowledge logic, and so forth.

The goals of the design is:

1. Allow far nodes to communicate using intermediate nodes.
2. To employ techniques to mitigate missed messages due to the fact the SX1276 is half-duplex, so can't hear messages when transmitting.
3. Do 1 and 2 considering the available data rate, which is very low.

## Message formats

The low level (layer 2) format is the one with the explicit header selected, so it is up to the chip to add a length, a CRC and so forth. This layer is not covered here, as from the SX1276 driver we directly get the *clean* bytes received. So this covers layer 3, that is the messages format implemented by FreakWAN.

The first byte is the message type byte. The following message types are defined:

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
* Bit 2: `Fragment`. This flag means that this message is a fragment of many, that should be reassembled in order to retrieve the full Data message. This specification does not yet cover fragmentation, it will be added later.
* Bit 3: `Media`. For message of type 'Data' this flag means that the message is not text, but some kind of media. See the Data messages section for more information.
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

Data messages may contain media in case this flag is set in the header
of the message:

* Bit 3: `Media`.

When this happens, the data inside the message is not some text in the form `nick:message`. Instead the first byte of the message is the media type ID, from 0 to 255. Right now only a media type is defined:

* Media type 0: FreakWAN Compressed Image (FCI). Small 1 bit color image.

```
+--------+------//------+-----------+-------------+----//
| type:8 | other fields | sender:48 | mediatype:8 | ... media data ...
+--------+------//------+-----------+-------------+----//
```

Devices receiving this message should try to show the bitmap on the
screen, if possible, or if the image is too big or they like any
graphical display ability, some text should be produced to make the user
aware that the message contains an image.

## ACK message

The ACK message is used to acknowledge the sender that some nearby device
actually received the message sent. ACKs are sent only when receiving
messages of type: DATA, and only if the `Relayed` flag is not set.

The goal of ACK messages are two:

1. They inform the sender of the fact at least some *near* nodes (immediately connected hops) received the message. The sender can't know, just by ACKs, the total reach of the message, but it will now if the number of receivers is non-zero.
2. Each sender takes a list of directly connected nodes, via the HELLO messages (see later in this document). When a sender transmits some data, it will resend it multiple times, in order to make delivery more likely. To save channel time, when a sender receives an ACK from all the known neighbor nodes, it must suppress further retransmissions of the message. In practice this often means that, out of 3 different transmission attempts, only one will be performed.

The reason why nodes don't acknowledge with ACKs messages that are relayed (and thus have the `Relayed` flag set) is the following:
* We can't waste channel time to make the sender aware of far nodes that received the message. For each message we would have to produce `N-1` ACKs (with N being the number of nodes), and even worse such ACKs would be relayed as well to reach the sender. This does not make sense, in practice: LoRa bandwidth is tiny. So the only point of sending ACKs to relayed messages would be to suppress retransmissions of relayed messages: this, however, is used in the first hop (as described before) only because we want to inform the original sender of the fact *somebody* received the message. However using this mechanism to just suppress retransmissions is futile: often the ACKs would waste more channel bandwidth than the time saved.

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

Devices receiving HELLO messages will compile a list of neighbors. A
device is removed from the list if we don't receive a HELLO message
from it for 10 minutes (this means we need to miss many successive
hello messages, in order to remove a device -- this is an important point,
since we need to account for the high probability of losing messages
for being in TX mode while some other node broadcasts).

Format:

```
+--------+---------+---------------+--------+------------\\
| type:8 | flags:8 | 46 bit sender | seen:8 | status message
+--------+---------+---------------+--------+------------\\
```

* The type id is set to the HELLO message type.
* Flags are currently unused for the HELLO message.
* The sender is the device ID of the sender.
* Seen is the number of devices this device is currently sensing, that is, the length of its neighbors list.
* The status message is a string composed of the nickname of the owner, then a semicolon, and a message that the user can set. Like:

    antirez:Hi there! I'm part of FreakWAN.

## Messages relay

Data messages with the `PleaseRelay` flag set are retransmitted by the nodes receiving them. The retransmission is the fundamental way in which the WAN is built. Imagine the following FreakWAN set of devices:

    A <------ 10 km -------> B <----- 10km -----> C

For a message sent by A to reach C, if we imagine a range of, for instance,
12 km, When B receives the messages created by A it must repeat the messages, so that C can also receive them.

To do so, FreakWAN uses the following mechanism:

1. A data message that has the `PleaseRelay` bit set, when received, is retransmitted multiple times, assuming its TTL is still greater than 1. The TTL of the message is decremented by one, the `Relayed` flag is set in the message, finally the message is send again *as it is*, without changing the sender address, but maintaining the original one.
2. Devices may chose to avoid retransmitting messages with a too high RSSI, in order to avoid using precious channel time without a good reason. It is of little interest that two very nearby devices retransmit their messages.
3. Retransmitted messages have the `Relayed` flag set, so ACKs are not transmitted by the receivers of those messages. FreakWAN ACKs only serve to inform the originator of the message that some neighbor device received the message, but are not used in order to notify of the final destinations of the message, as this would require a lot of channel time and is quite useless. For direct messages between users, when they will be implemented, the acknowledge of reception can be created on top of the messaging system itself, sending an explicit reply.
4. Each message received and never seen before is relayed N times, with N being a configuration inside the program defaulting to 3. However users may change it, depending on the network nodes density and other parameters.

## Listen Before Talk

FreakWAN implementations are required to implement Listen Before Talk, in order to avoid sending messages if they detect some other valid LoRa transmission (either about FreakWAN or not) currently active. In this implementation, this feature is accomplished by reading the LoRa radio status register and avoiding transmitting if the set of bits reports an incoming packet being received.

LBT is a fundamental improvement for the performance of this protocol, since a major issue with this kind of routing, where every packet is sent and then relayed to everybody on the same frequency, is packet collisions.
