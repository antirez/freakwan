# FreakWAN

FreakWAN is an effort to create a LoRa-based open WAN network, completely independent from Internet and the cellular phones networks. The network built with FreakWAN has two main goals:

1. To provide both a plaintext and an encrypted distributed chat system, that can be used by technology amateurs, or in places where internet is not available and during disasters.
2. As a side effect of the first goal, to create a robust protocol over LoRa to support other applications, like sensors data collection, home automation applications, not having the usual range limitations of OOK/FSK communcation, and so forth.

Our goal is to cover parts of the Sicily with such a network. The code
will be freely available to anyone wanting to build their own LoRa
WANs on top of this software. The main features of our implementation and
protocol are the following:

* A distributed network based on LoRa and broadcast routing.
* Basic chat features, ability to send medias (like small images).
* Different group chat or data channels (including one-to-one chats) using encryption to separate them.
* Configurable number of retransmissions with random delays.
* First-hop acknowledges of messages sent.
* Symmetric encryption with AES in CBC mode, with support for integrity detection and multiple concurrent keys: each group of clients knowing a given key is part of a virtual group. The network is collaborative for encrypted messages: even nodes that are not able to decrypt a given message can broadcast it, since the encrypted part is not vital to perform relaying of messages.
* Sensing of nearby nodes, via `HELLO` messages (advertising).
* Bandwidth usage mitigation features.
* Duty cycle tracking.
* Local storage of messages in the device flash, with automatic deletion of old messages.
* Simple home-made driver for the SX1276 and SX1262 LoRa chip. In general, no external dependencies. Runs with vanilla MicroPython installs.
* OLED terminal alike output. OLED burning pixels protection.
* CLI interface via USB serial and Bluetooth LE.
* IRC interface: the device can work as a bot over the IRC protocol.
* Simple to understand, hackable code base.

This code is currently a functional work in progress, designed to work with the following ESP32-based devices:

1. LILYGO TTGO T3 v2 1.6 LoRa module.
1. LILYGO TTGO T3-S3 v1.2 LoRa module (2.4 Ghz version not tested/supported).
2. LILYGO TTGO T Beam LoRa module.
3. LILYGO T-WATCH S3.

However changing the pins in the configuration, to adapt it to other ESP32 modules that have an SX1276, SX1262 LoRa chips, and an SSD1306 or ST7789 display (or no dislay, in headless mode), should be very little work. T-ECHO devices are also supported, even if with less features, in the C port of FreanWAN, under the `techo-port` directory, but the T-ECHO port is still alpha quality software.

**FreakWAN is implemented in MicroPython**, making use only of default libraries.

# Installation

* Install [MicroPython](https://micropython.org/download/) on your device. Follow this instructions to get the right MicroPython version:
1. **MicroPython versions > 1.19.1 and < 1.22.2 have buggy bluetooth stack**, so make sure to use 1.22.2 (or greater) or if you want to stick with something old, use 1.19.1.
2. Don't bother installing a MicroPython specific for the LILYGO devices. Just grab the standard ESP32 image (but not for the T3-S3, read more).
3. The T3-S3 (and probably the T-BEAM S3, which we don't support at the moment, because we don't have the device) have a 4MB flash which is not compatible with the default MicroPython image for 8MB flash. You can find a working image directly inside this repository **under the `device` directory**.
4. To flash your device, follow the MicroPython instructions in the download page of your device. For the T3-S3, don't forget to press the *boot* button while powering it up, otherwise you will not be able to flash it. Then, with `esptool.py`, perform the `erase_flash` command followed by the `write_flash` with the **parameters specified in the MicroPython download page**.
* Clone this repository, and edit `wan_config.py` to set your nickname and status message, set the frequency according to your device. **Warning**: make sure to set the right frequency based on the LoRa module you own, and make sure your **antenna is already installed** before using the software, or you **may damage your hardware**, (but I would like to report that we started the device with the wrong freuqnecy several times and nothing happened: still, proceed at your own risk).
* Copy one of the files inside the `devices` folder in the main folder as `device_config.py`, for instance if I have a T3 v2 1.6 device, I will do:

    cp devices/device_config.t3_v2_1.6.py ./device_config.py

* Transfer all the `.py` files in the root directory of this project in your device. To transfer the files, you can use **mpremote** (`pip3 install mpremote` should be enough), or an alternative (and slower, but sometimes more compatible) tool that we wrote, called [talk32](https://github.com/antirez/talk32). Talk32 is not as fast as mpremote at transferring files, but sometimes mpremote does not work with certain devices and talk32 does (and the other way around).

(**NOTE**: you need the `:` below, is not an error)

    mpremote cp *.py :

or

    talk32 /dev/tty.usbserial001 put *.py

Please note that you **don't need** both the command lines. Just one depending on the tool you use.

* Restart your device: you can either power it off/on, or use `mpremote repl` and hit `Ctrl_D` to trigger a soft reset. Sometimes devices also have a reset button. If everything is fine you will see the splash screen and then the program version.
* If you are using a T-WATCH S3, or other recent Lyligo devices based on ESP32-S3, and your splash screen freezes (the waves should move and then the splash screen should disappear, if everything works well), please try to disable BLE from `wan_config.py`.

# Usage

The two simplest ways to send commands to the device, write messages
that will be broadcasted and also receive messages sent by other
users, it is to use the USB or Bluetooth serial.

## Serial CLI

To obtain a serial command line interface, make sure the device is connected
via an USB cable with your computer. Than connect to the device serial with
`talk32`, `minicom`, `screen` or whatever serial terminal you want to use.
Normally the bound rate is 115200. Example of command lines and tools you could use:

    mpremote repl

or

    talk32 /dev/tty.usbserial001 repl

or

    screen /dev/tty.usbserial001 115200

Of course the name of the device is just an example. Try `ls /dev/tty*` to see the list of possible device names in your computer.

Once you connect, you will see the device logs, but you will also be able
to send bang commands or messages to the chat (see below).

## Bluetooth low energy CLI

It is possible to use the device via Bluetooth LE, using one of the following applications:
* Android: install one of the many BLE UART apps available. We recommend the [Serial Bluetooth Terminal app](https://play.google.com/store/apps/details?id=de.kai_morich.serial_bluetooth_terminal&hl=en&gl=US). It works great out of the box, but for the best experience open the settings, go to the *Send* tab, and select *clear input on send*. An alternative is [nRF Toolbox](https://www.nordicsemi.com/Products/Development-tools/nrf-toolbox), select the UART utility service, connect to the device and send a text message or just `!help`.
* iPhone: [BLE Terminal HM-10](https://apps.apple.com/it/app/ble-terminal-hm-10/id1398703795?l=en) works well and is free. There are other more costly options.
* Linux Desktop: install [Freakble](https://github.com/eriol/freakble) following the project README.
* For MacOS, there is a BLE UART app directly inside this software distribution under the `osx-bte-cli` directory. Please read the README file that is there.

## Sending commands and messages

Using one of the above, you can talk with the device, and chat with other users around, sending CLI commands.
If you just type some text, it will be sent as message in the network. Messages received from the network are also shown in the serial console.
If you send a valid command starting with the `!` character, it will be executed as a command, in order to show information, change the device configuration and so forth. For now you can use:
* `!automsg` [on/off] to disable enable automatic messages used for testing.
* `!bat` to show the battery level.
* `!preset <name>` to set a LoRa preset. Each preset is a specific spreading, bandwidth and coding rate setup. To see all the available presets write `!preset help`.
* `!sp`, `!bw`, `!cr` to change the spreading, bandwidth and coding rate independently, if you wish.
* `!pw` changes the TX power. Valid values are from 2 to 20 (dbms). Default is 17dbms.
* `!ls` shows nodes around. This is the list of nodes that your node is able to *sense*, via HELLO messages.
* `!font big|small` will change between an 8x8 and a 5x7 (4x6 usable area) font.
* `!image <image-file-name>` send an FCI image (see later about images).
* `!last [<count>]` show the last messages received, taking them from the local storage of the device.
* `!config [save|reset]` to save (or reset) certain configuration parameters (LoRa radio parameters, automsg, irc, wifi, ...) that will be reloaded at startup.
* `!irc <stop|start>` starts or stops the IRC interface.
* `!telegram <start|stop|token>` starts, stops and sets the token of the Telegram bot.
* `!wifi help`, to see all the WiFi configuration subcommands. Using this command you can add and remove WiFi networks, connect or disconnect the WiFi (required for the IRC and Telegram interface), and so forth.
* `!quiet <yes|no>`, to enable quiet mode (default is off). In this mode, the device sends only the smallest amount of data needed, that is the data messages that we want to send. No ACKs are sent in reply to data messages, nor HELLO messages to advertise our presence in the network. Packets are not relayed in this mode, nor data is transmitted multiple times. Basically this mode is designed to save channel bandwidth, at the expense of advanced FreakWAN features, when there are many active devices and we want to make sure the LoRa channel is not continuously busy.
* `!b0`, this is the same as pressing the button 0 on the devices (if they have one). Will switch the device screen to the next view.

New bang commands are added constantly, so try `!help` to see what is available. We'll try to take this README in sync, especially after the first months of intense development will be finished.

## Using the device via Telegram

When FreakWAN is located in some fixed location with WiFi access, it is possible to put it online as a Telegram bot. This way it is possible to receive the messages the device receives via LoRa as Telegram messages, and at the same time it is possible to send commands and messages writing to the bot.

To use this feature, follow the instructions below:

1. Create your bot using the Telegram [@BotFather](https://t.me/botfather).
2. After obtaining your bot token (it's basically the bot API key) use the following commands in the FreakWAN cli (either via USB or BLE) or alternatively edit `wan_config.py` to set the same parameters.

    !wifi add networkname password
    !wifi start networkname
    !telegram token <your-bot-token-here>
    !telegram start

Now use your Telegram application in order to sent `!help` to the bot, and wait for the reply. If you can receive the reply correclty, Freakwan will also set the *target* of your messages, that is, the account you used to talk with the bot the first time. Now you are ready to save your configuration with:

    !config save

## Using the device via IRC

FreakWAN is able to join IRC, as a bot. It can receive messages and commands via IRC, and also show messages received via LoRa into an IRC channel. Edit `wan_config.py` and enable IRC by setting the enabled flag to True, and configuring a WiFi network. Upload the modified file inside the device and restart it. Another way to enable IRC is to use bang commands via Bluetooth, like that:

    !wifi add networkname password
    !wifi start networkname
    !irc start
    !config save (only if you want to persist this configuration)

The device, by default, will enter the `##Freakwan-<nickname>` channel of `irc.libera.chat` (please, note the two `#` in the channel name), and will listen for commands there. The same commands you can send via Bluetooth are also available via IRC. Because of limitations with the ESP32 memory and the additional MicroPython memory usage, SSL is not available, so FreakWAN will connect to IRC via the TCP port 6667, which is not encrypted.

## Encrypted messages

By default LoRa messages are sent in clear text and will reach every device that is part of the network, assuming it is configured with the same LoRa frequency, spreading, bandwidth and coding rate. However, it is possible to send encrypted messages that will reach only other users with a matching symmetric key. For instance, if Alice and Bob want to communicate in a private way, they will set the same key, let's say `abcd123`, in their devices. Bob will do:

    !addkey alice abcd123

While Alice will do:

    !addkey bob abcd123

(Note: they need to use much longer and hard to guess key! A good way to generate a key is to to combine a number of words and numbers together, or just generate a random 256 bit hex string with any available tool).

Now, Alice will be able to send messages to Bob, or the other way around, just typing:

    #bob some message

Bob will see, in the OLED display of the device, and in the Android application, if connected via BTE, something like that:

    #alice Alice> ... message ...

Encrypted messages that are correctly received and decoded are shown as:

    #<keyname> Nick> message

Each device can have multiple keys. The device will try to decrypt each encrypted message with all the keys stored inside the key chain (the device flash memory, under the `keys` directory -- warning! keys are not encrypted on the device storage).

If many users will set the same key with the same name, they are effectively creating something like an *IRC channel* over LoRa, a chat where all such individuals can talk together.

This is the set of commands to work with encrypted messages:

    #<keyname> some message     -- send message with the given key.
    !addkey keyname actual-key-as-a-string  -- add the specified key.
    !delkey keyname             -- remove the specified key.
    !keys                       -- list available keys.
    !usekey keyname             -- set the specified key as default to send all the next messages, without the need to resort to the #key syntax.
    !nokey                      -- undo !usekey, return back to plaintext.

## Sending images

FreakWAN implements its own very small, losslessy [compressed 1 bit images](https://github.com/antirez/freakwan/blob/main/fci/README.md), as a proof of concept that we can send small media types over LoRa. Images are very useful in order to make the protocol more robust when working with very long packets (that have a very large *time on air*). Inside the `fci` directory of this repository you will find the specification of the image format and run length compression used, and a tool to convert small PNG files (255x255 max) into FCI images. For now, only images that are up to 200 bytes compressed can be transmitted.

Once you have the FCI images, you should copy them into the `images` directory inside your device (again, using ampy or talk32 or any other tool). Then you can send the images using the `!image` command using the bluetooth CLI.

You can find a couple test FCI images under `fci/testfci`. They are all less than 200 bytes, so it is possible to send them as FreakWAN messages.

## Power management

Right now, for the LILYGO TTGO T3 device, we support reading the battery level and shutting down the device when the battery is too low, since the battery could be damaged if it is discharged over a certain limit. To prevent such issues, when voltage is too low, the device will go in deep sleep mode, and will flash the led 3 times every 5 seconds. Then, once connected again to the charger, when the battery charges a bit, it will restart again.

For the T Beam, work is in progress to provide the same feature. For now it is better to disable the power management at all, by setting `config['sleep_battery_perc']` to 0 in the `wan_config.py` file.

If you plan to power your device with a battery that is not 3.7v, probably it's better to disable this feature from the configuration, or the device may shut down because it is sensing a too low voltage, assuming the battery is low.

# FreakWAN network specification

The rest of this document is useful for anybody wanting to understand the internals of FreakWAN. The kind of messages it sends, how messages are relayed in order to reach far nodes, the retransmission and acknowledge logic, and so forth.

The goals of the design is:

1. Allow far nodes to communicate using intermediate nodes.
2. To employ techniques to mitigate missed messages due to the fact LoRa is inherently half-duplex, so can't hear messages when transmitting.
3. Do 1 and 2 considering the available data rate, which is very low.

## Message formats

The low level (layer 2) format is the one with the explicit header selected, so it is up to the chip to add a length, a CRC and so forth. This layer is not covered here, as from the SX1276 / SX1262 driver we directly get the *clean* bytes received. So this covers layer 3, that is the messages format implemented by FreakWAN.

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

* Bit 0: `Relayed`. Set if the message was repeated by some node that is not the originator of the message. Relayed messages are not acknowledged.
* Bit 1: `PleaseRelay`. If this flag is set, other receivers of the message will try to repeat the message, so that it can travel further in the WAN.
* Bit 2: `Fragment`. This flag means that this message is a fragment of many, that should be reassembled in order to retrieve the full Data message.
* Bit 3: `Media`. For message of type 'Data' this flag means that the message is not text, but some kind of media. See the Data messages section for more information.
* Bit 4: `Encr`. For messages of type 'Data' this flag means that the message is encrypted.
* Bit 5-7: Reserved for future uses. Should be 0.

Currently not all the message types are implemented.

## DATA message

Format:

```
+--------+---------+---------------+-------+-----------+------------------//
| type:8 | flags:8 | message ID:32 | TTL:8 | sender:48 | Message string:...
+--------+---------+---------------+-------+-----------+------------------//
```

Note that there is no message length, as it is implicitly encoded in the
previous layer. The message string is in the following format:

```
+--------+---------------------//
| nlen:8 | nick+message text
+--------+---------------------//
```

Where `nlen` is a byte representing the nick name length inside the
message, as an unsigned 8 bit integer, and the rest is just the nickname
of the specified length concatenated with the actual message text, without
any separator, like in the following example:

    "\x04AnnaHey how are you?"

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

When this happens, the data inside the message is not some text in the form `nick`+`message`. Instead the first byte of the message is the media type ID, from 0 to 255. Right now only two media types are defined:

* Media type 0: FreakWAN Compressed Image (FCI). Small 1 bit color image.
* Media type 1: Sensor reading.

```
+--------+------//------+-----------+-------------+----//
| type:8 | other fields | sender:48 | mediatype:8 | ... media data ...
+--------+------//------+-----------+-------------+----//
```

Devices receiving this message should try to show the bitmap on the
screen, if possible, or if the image is too big or they lack any
graphical display ability, some text should be produced to make the user
aware that the message contains an image.

## ACK message

The ACK message is used to acknowledge the sender that some nearby device
actually received the message sent. ACKs are sent only when receiving
messages of type: DATA, and only if the `Relayed` flag is not set.

The goal of ACK messages are two:

1. They inform the sender of the fact at least some *near* nodes (immediately connected hops) received the message. The sender can't know, just by ACKs, the total reach of the message, but it will know if the number of receivers is non-zero.
2. Each sender takes a list of directly connected nodes, via the HELLO messages (see later in this document). When a sender transmits some data, it will resend it multiple times, in order to make delivery more likely. To save channel time, when a sender receives an ACK from all the known neighbor nodes, it must suppress further retransmissions of the message. In practice this often means that, out of 3 different transmission attempts, only one will be performed.

The reason why nodes don't acknowledge with ACKs messages that are relayed (and thus have the `Relayed` flag set) is the following:
* We can't waste channel time to make the sender aware of far nodes that received the message. For each message we would have to produce `N-1` ACKs (with N being the number of nodes), and even worse such ACKs would be relayed as well to reach the sender. This does not make sense, in practice: LoRa bandwidth is tiny. So the only point of sending ACKs to relayed messages would be to suppress retransmissions of relayed messages: this, however, is used in the first hop (as described before) only because we want to inform the original sender of the fact *somebody* received the message. However using this mechanism to just suppress retransmissions is futile: often the ACKs would waste more channel bandwidth than the time saved.

Format:

```
+--------+---------+---------------+-----------------+---------------+
| type:8 | flags:8 | message ID:32 | 8 bits ack type | 48 bit sender |
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
| type:8 | flags:8 | 48 bit sender | seen:8 | status message
+--------+---------+---------------+--------+------------\\
```

* The type id is set to the HELLO message type.
* Flags are currently unused for the HELLO message.
* The sender is the device ID of the sender.
* Seen is the number of devices this device is currently sensing, that is, the length of its neighbors list.
* The status message is exactly like in the DATA message format: a string composed of one byte length of the nickname, and then the nickname of the owner and the message that was set as status message. Like:

    "\x07antirezHi there! I'm part of FreakWAN."

## Messages relay

Data messages with the `PleaseRelay` flag set are retransmitted by the nodes receiving them. The retransmission is the fundamental way in which the WAN is built. Imagine the following FreakWAN set of devices:

    A <------ 10 km -------> B <----- 10km -----> C

For a message sent by A to reach C, if we imagine a range of, for instance,
12 km, When B receives the messages created by A it must repeat the messages, so that C can also receive them.

To do so, FreakWAN uses the following mechanism:

1. A data message that has the `PleaseRelay` bit set, when received, is retransmitted multiple times, assuming its TTL is still greater than 1. The TTL of the message is decremented by one, the `Relayed` flag is set in the message, finally the message is sent again *as it is*, without changing the sender address, but maintaining the original one.
2. Devices may chose to avoid retransmitting messages with a too high RSSI, in order to avoid using precious channel time without a good reason. It is of little interest that two very nearby devices retransmit their messages.
3. Retransmitted messages have the `Relayed` flag set, so ACKs are not transmitted by the receivers of those messages. FreakWAN ACKs only serve to inform the originator of the message that some neighbor device received the message, but are not used in order to notify of the final destinations of the message, as this would require a lot of channel time and is quite useless. For direct messages between users, when they will be implemented, the acknowledge of reception can be created on top of the messaging system itself, sending an explicit reply.
4. Each message received and never seen before is relayed N times, with N being a configuration inside the program defaulting to 3. However users may change it, depending on the network nodes density and other parameters.

# Listen Before Talk

FreakWAN implementations are required to implement Listen Before Talk, in order to avoid sending messages if they detect some other valid LoRa transmission (either about FreakWAN or not) currently active. In this implementation, this feature is accomplished by reading the LoRa radio status register and avoiding transmitting if the set of bits reports an incoming packet being received.

LBT is a fundamental improvement for the performance of this protocol, since a major issue with this kind of routing, where every packet is sent and then relayed to everybody on the same frequency, is packet collisions.

# Encryption

FreakWAN default mode of operation is as unencrypted everybody-can-talk
open network. In this mode, messages can be spoofed, and different
persons (nicks) or nodes IDs can be impersonated by other devices
very easily.

For this reason it is also possible to use encryption with pre-shared
symmetric keys. Because of the device limitations and the standard library
provided by MicroPython, we had to use an in-house encryption mode based
on AES and SHA256.

## High level encryption scheme

Each device can store multiple symmetric keys, associated with
a key name. Every time an encrypted message is received, all the keys
are tested against the packet, and if a matching key is found (see
later about the mechanism to validate the key) the message is correctly
received, and displayed with the additional information of the key
name, in order to make the user aware that this is an encrypted message
that was decrypted with a specific key.

So, for example, if a key is shared between only two users, Alice and
Bob, then Alice will store the `xyz` key with the name "BoB", ad Bob
will store the same `xyz` key with the name "Alice". Every time Alice
receives an encrypted message with such key, it will see:

    #Bob bob> Hi Alice, how are you?

Where the first part is `#<keyname>`, and the rest of the message is
the normal message, nick and text, or media type, as normally displayed.

Similarly if the same key is shared among a group of users, the effect
will be to participate into a group chat.

Keys must be shared using a protected channel: either via messaging
systems like Whatsapp or Signal, or face to face with the interested
users. Optionally the system may decide to encrypt local keys using
a passphrase, so that keys can't be extracted from the device when
it is non operational.

## Encrypted packets and algorithm

Only data messages are encrypted. ACKs, HELLO and other messages
remain unencrypted.

The first four standard header fields of an encrypted packet are not
encrypted at all: receivers, even without a key at hand, need to be able to
check the message type and flags, the TTL (in case of relay), the message UID
(to avoid reprocessing) and so forth. The only difference between the first
7 bytes (message type, flags, UID, TTL) of an ecrpyted and unencrypted message
is that the `Encr` flag is set. Then, if such
flag is set and the packet is thus encrypted, a 4 bytes initialization
vector (IV) follows. This is the unencrypted part of the packet. The
encrypted part is as the usual data as found in the DATA packet type: 6 bytes
of sender and the data payload itself. However, at the end of the packet,
there is an additional (not encrypted) 10 bytes of HMAC (truncated
HMAC-256), used to check integrity, and even to see if a given key is actually
decrypting a given packet correctly. The checksum computation is specified later.

This is the representation of the message described above:

```
+--------+---------+-------+-------+-------+-----------+--//--+------+
| type:8 | flags:8 | ID:32 | TTL:8 | IV:32 | sender:48 | data | HMAC |
+--------+---------+-------+-------+-------+-----------+--//--+------+
                                           |                  |
                                           `- Encrypted part -'
```

The 'IV' is the initialization vector for the CBC mode of AES, that is
the algorithm used for encryption. However it is used together with all
the unencrypted header part, from the type field, at byte 0, to the last byte
of the IV. So the initialization vector used is a total 11 bytes, of which
at least 64 bits of pseudorandom data.

The final 10 bytes HMAC is computed using HMAC-SHA256, truncated to 10 bytes, but **the last 4 bits are set to the padding length of the message**, so actually of the 80 bits HMAC, only the first 76 are used. The last byte least significant four bits tell us how many bytes to discard from the decrypted payload, because of AES padding.

The AES key and the HMAC key are different, but derived from the same master key. The derivation is performed as such: Given the unique key `k`, we derive the two keys with as:

    aes-key = first 16 bytes of HMAC-SHA256(k,"AES14159265358979323846")
    mac-key = HMAC-SHA256(k,"MAC26433832795028841971")

## Encryption

To encrypt:

1. Build the first four fields of the packet header as described above.
2. Renerate a random 4 bytes IV and append it.
3. Set TTL to 0 (but save the original value), and clear the `Relayed` flag bit, also saving the original flag value.
3. Encrypt the payload with AES in CBC mode, using aes-key as key, and using as IV the first 11 bytes of the packet. Pad the packet with zeroes so that it is multiple of 16 bytes (AES block). Remember the padding used to reach the AES block size as "PADLEN". Append the encrypted payload to the packet.
4. Perform HMAC-SHA256(mac-key,packet) of all the packet built so far.
5. Append the first 10 bytes of the HMAC to the packet, but replace the last 4 bits with PADLEN as unsigned 4 bit integer.
6. Restore TTL and `Relayed` flag.

Decrypting is very similar. When a packet arrives, we clear the TTL and
`Relayed` bit (saving the original values). We also store the last 4 bits
of the HMAC as PADLEN, and clear those bits. Then, for all the all the keys
we have in memory, one after the other, we see if we can find one for which
we can recompute the HMAC of the message (minus the last 10 bytes), trucate
it to 10 bytes, clearing the last 4 bits, and check if it matches with the
final 10 bytes of the packet.

If a match is found, we can decrpyt the message with AES in CBC mode,
discard the final PADLEN zero bytes (checking they are actually zero
as an additional check against implementation bugs), and process it.

## Relaying of encrypted messages

The receiver of the packet has all the information required in order to
relay the packet: we want the network to be collaborative even for messages
that are not public. If the PleaseRelay flag is set, nodes should retransmit
the message as usually, decrementing that TTL and setting the `Relayed` flag: the TTL and this flag are not part of the CHECKSUM computation, nor of the IV (they are set to 0), so can be modified by intermediate nodes without invalidating the packet. Similarly, the message UID is exposed in the unencrypted header, so
nodes without a suitable key for the message can yet avoid re-processing the
message just saving its UID in the messages cache.

## Security considerations

* The encryption scheme described here was designed in order to use few bytes of additional space and the only encryption primitive built-in in MicroPython that was stable enough: the SHA256 hash and AES.
* Because of the device and LoRa packets size and bandwidth limitations, the IV is shorter than one would hope. However it is partially compensated by the fact that the message UID is also part of the set of bytes used as initialization vector (see the encryption algorithm above). So the IV is actually at least 64 bits of pseudorandom data. For the attacker, it will be very hard to find two messages with the same IV, and even so the information disclosed would be minimal.
* The `sender` field of the message is part of the encrypted part, thus encrypted messages don't discose nor the sender, that is encrypted, nor the received, that is implicit (has the key) of the message.

# Packets fragmentation (proposal not implemented)

LoRa packets are limited to 256 bytes. There is no way to go over such
limitation (it is hardcoded in the hardware), and it would also be useless,
since the long time on air means that, after a certain length, it is hard to
take a good frequency reference: communication errors would be inevitable.

So the FreakWAN protocol supports fragmentation, for use cases when it is
useful to transmit messages up to a few kilobytes at max. Fragmentation is
only supported for DATA type message (the other message types don't need,
to be larger than the LoRa packet size), and works both for clear text
and encrypted messages.

In the sender size, when the total length of the packet would be more than
`MAXPACKET` total bytes (that may be configured inside the app), the data
payload is split in roughly equally sized packets. The last packet may have a
byte more in case the data length is not multiple of the number of packets.

**Important**: `MAXPACKET` must be choosen so that it is always possible to transmit
two bytes more than its value, since the data section will have two additional
bytes used for the fragmentation metadata.

So, for instance, if the data section (nick + data o media) of a DATA packet
is 1005 bytes, and `MAXPACKET` is set to 200 bytes, the number of total packets
required is the integer result of the following division:

    NUMPACKETS = (DATALEN+MAXPACKET-1) / MAXPACKET

That is:

    NUMPACKETS = (1005+199)/200 = 6

Each of the packets will have the following size:

    BASESIZE = 1005/6 = 167

However `167*6` = just 1002 bytes. So we also calculate a reminder size:

    REM = DATALEN - BASESIZE*NUMPACKETS
    REM = 1005 - (167*6) = 3

And we add a single additional byte of data to the first REM packets
we generate during the fragmentation, so the length of the packets
will be:

* Packet 1: 168
* Packet 2: 168
* Packet 3: 168
* Packet 4: 167
* Packet 5: 167
* Packet 6: 167

That is a total of 1005 bytes. The strategy used attempts at generating packets
of roughly the same size, so that each packet has a better probability of
being transmitted correctly. For our use case, to transmit the first N-1 full
packets at the maximum length, and then a final small packet, would not be
optimal.

## Fragment header and data section

Each fragment will be sent as a DATA message is exactly like a normal DATA
message, with the following differences:

1. The `Fragment` flag is set in the header flags section.
2. At the end of the fragment data, there are two 8 bit unsigned integers, appended to the data itself.

For instance, in the example above, the first packet would have 168 bytes
of data terminated by two additional bytes:

```
//-----------------------+------------+-------------+
... 168 byts of data ... | frag-num:8 | tot-frags:8 |
/.-----------------------+------------+-------------+
```

Where `frag-num` is the number of the fragment, identifying its position
among all the fragmnets, and `tot-frags` is the total number of
fragments. The total length of the data is implicit, and is not direcly
available.

The receiver will accumulate (for a given maximum time) message fragments
having the same Message ID field value. Once all the fragments are
received, the origianl message is generated from the fragments, where the
`Fragment` flag is cleared, the data sections of all the fragments are glued
together (but discarding the last two bytes of each packet), and finally the
message is passed for processing to the normal FreakWAN path inside the
FreakWAN stack. The software should make sure that fragments don't accumulate
forever in case some fragment is missing: after a given time, if no full
reassembly was possible, fargments should expire and the memory should be
freed.


