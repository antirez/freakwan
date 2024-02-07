# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import struct, time, urandom, machine
from micropython import const
 
# Message types
MessageTypeData = const(0)
MessageTypeAck = const(1)
MessageTypeHello = const(2)
MessageTypeBulkStart = const(3)
MessageTypeBulkData = const(4)
MessageTypeBulkEND = const(5)
MessageTypeBulkReply = const(6)

# Message flags
MessageFlagsNone = const(0)               # No flags
MessageFlagsRelayed = const(1<<0)         # Repeated message
MessageFlagsPleaseRelay = const(1<<1)     # Please repeat this message
MessageFlagsFragment = const(1<<2)        # One fragment of many
MessageFlagsMedia = const(1<<3)           # Message contains some media
MessageFlagsEncr = const(1<<4)            # Message is encrypted

# Virtual flags: not really in the packet header, but added
# in the message object representing the packet to provide
# further information.
MessageFlagsBadCRC = const(1<<8)          # Message CRC is bad

# Media types
MessageMediaTypeImageFCI = const(0)
MessageMediaTypeSensorData = const(1)

# Sensor data media type readings
MessageSensorDataTemperature = const(0)
MessageSensorDataAirHumidity = const(1)
MessageSensorDataGroundHumidity = const(2)
MessageSensorDataBattery = const(3)

# The message object represents a FreakWAN message, and is also responsible
# of the decoding and encoding of the messages to be sent to the "wire".
class Message:
    def __init__(self, nick="", text="", media_type=255, media_data=False, uid=False, ttl=15, mtype=MessageTypeData, sender=False, flags=0, rssi=0, ack_type=0, seen=0, key_name=None):
        self.ctime = time.ticks_ms() # To evict old messages

        # send_time is only useful for sending, to introduce a random delay.
        self.send_time = self.ctime

        # Number of times to transmit this message. Each time the message
        # is transmitted, this value is reduced by one. When it reaches
        # zero, the message is removed from the send queue.
        self.num_tx = 1
        self.acks = {}  # Device IDs we received ACKs from
        self.type = mtype
        self.flags = flags
        self.nick = nick
        self.text = text
        self.media_type = media_type
        self.media_data = media_data
        self.uid = uid if uid != False else self.gen_uid()
        self.sender = sender if sender != False else self.get_this_sender()
        self.ttl = ttl              # Only DATA
        self.ack_type = ack_type    # Only ACK
        self.seen = seen            # Only HELLO
        self.rssi = rssi
        self.key_name = key_name
        self.no_key = False         # True if it was not possible to decrypt.

        # If key_name is set, encoded messages will be encrypted, too.
        # When messages are decoded, key_name is set to the key that
        # decrypted the message, if any.

        # Sometimes we want to supporess sending of packets that may
        # already be inside the TX queue. Instead of scanning the queue
        # to look for the message, we just set this flag to True.
        self.send_canceled = False

    # Generate a 32 bit unique message ID.
    def gen_uid(self):
        return urandom.getrandbits(32)

    # Get the sender address for this device. We just take 6 bytes
    # of the device unique ID.
    def get_this_sender(self):
        return machine.unique_id()[-6:]

    # Return the sender as a printable hex string.
    def sender_to_str(self):
        if self.sender:
            s = self.sender
            return "%02x%02x%02x%02x%02x%02x" % (s[0],s[1],s[2],s[3],s[4],s[5])
        else:
            return "ffffffffffff"

    # Turn the message into its binary representation.
    def encode(self,keychain=None):
        if self.no_key == True:
            # Message that we were not able to decrypt. In this case
            # we saved the packet, and we just need to encode the
            # plaintext header and concatenate the saved packet from the
            # IV field till the end.
            return struct.pack("<BBLB",self.type,self.flags,self.uid,self.ttl)+self.packet[7:]
        elif self.type == MessageTypeData:
            # Encode with the encryption flag set, if we are going to
            # encrypt the packet.
            encr_flag = MessageFlagsEncr if self.key_name else MessageFlagsNone
            encoded = struct.pack("<BBLB6sB",self.type,self.flags|encr_flag,self.uid,self.ttl,self.sender,len(self.nick))+self.nick
            if self.flags & MessageFlagsMedia:
                encoded += bytes([self.media_type])+self.media_data
            else:
                encoded += self.text

            # Encrypt if needed and if a keychain was provided.
            if self.key_name:
                if keychain:
                    encoded = keychain.encrypt(encoded,self.key_name)
                else:
                    printf("Warning: no keychain provided to Message.encode(). Message with key_name set will be unencrypted.")
            return encoded
        elif self.type == MessageTypeAck:
            return struct.pack("<BBLB",self.type,self.flags,self.uid,self.ack_type)+self.sender
        elif self.type == MessageTypeHello:
            return struct.pack("<BB6sBB",self.type,self.flags,self.sender,self.seen,len(self.nick))+self.nick+self.text
        else:
            print("WARNING Message.encode() unknown msg type",self.type)
            return None

    # Fill the message with the data found in the binary representation
    # provided in 'msg'.
    def decode(self,msg,keychain=None):
        try:
            mtype,flags = struct.unpack("<BB",msg)

            # If the message is encrypted, try to decrypt it.
            if mtype == MessageTypeData and flags & MessageFlagsEncr:
                if not keychain:
                    printf("Encrypted message received, no keychain given")
                    plain = None
                else:
                    plain = keychain.decrypt(msg)

                # Messages for which we don't have a valid key
                # are returned in a "raw" form, useful only for relaying.
                # We signal that the message is in this state by
                # setting .no_key to True. We also decode what is in the
                # unencrypted part of the header.
                if not plain:
                    self.type,self.flags,self.uid,self.ttl = struct.unpack("<BBLB",msg)
                    self.no_key = True
                    self.packet = msg # Save the encrypted message.
                    return True

                # If we have the key, the message is now decrypted.
                # We can continue with the normal code path after
                # populating key_name.
                self.key_name = plain[0]
                msg = plain[1]

            # Decode according to message type.
            if mtype == MessageTypeData:
                self.type,self.flags,self.uid,self.ttl,self.sender,nick_len = struct.unpack("<BBLB6sB",msg)
                self.nick = msg[14:14+nick_len].decode("utf-8")
                msg = msg[14+nick_len:] # Discard header and nick

                if self.flags & MessageFlagsMedia:
                    self.media_type = msg[0]
                    self.media_data = msg[1:]
                else:
                    self.text = msg.decode("utf-8")
                return True
            elif mtype == MessageTypeAck:
                self.type,self.flags,self.uid,self.ack_type,self.sender = struct.unpack("<BBLB6s",msg)
                return True
            elif mtype == MessageTypeHello:
                self.type,self.flags,self.sender,self.seen,nick_len = struct.unpack("<BB6sBB",msg)
                self.nick = msg[10:10+nick_len].decode("utf-8")
                self.text = msg[10+nick_len:].decode("utf-8")
                return True
            else:
                print("!!! Decoding message: wrong message type %d" % mtype)
                return False
        except Exception as e:
            print("!!! Message decode error msg="+str(msg)+" err="+str(e))
            return False

    # Create a message object from the binary representation of a message.
    def from_encoded(encoded,keychain):
        m = Message()
        if m.decode(encoded,keychain):
            return m
        else:
            return False

    # Turn the media data in the message into a string that can be parsed
    # by other programs.
    def sensor_data_to_str(self):
        l = len(self.media_data)
        off = 0
        res = ""
        while l > 0:
            fieldtype = self.media_data[off]
            off += 1
            l -= 1
            if fieldtype == MessageSensorDataTemperature or \
               fieldtype == MessageSensorDataAirHumidity or \
               fieldtype == MessageSensorDataGroundHumidity or \
               fieldtype == MessageSensorDataBattery:
                if l < 4: return "field data missing"
                val = struct.unpack("f",self.media_data[off:])
                off += 4
                l -= 4
                res += "%d:%.2f " % (fieldtype, val[0])
            else:
                return "field type error"
        return res
