# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import struct, time, urandom, machine
 
# Message types
MessageTypeData = 0
MessageTypeAck = 1
MessageTypeHello = 2
MessageTypeBulkStart = 3
MessageTypeBulkData = 4
MessageTypeBulkEND = 5
MessageTypeBulkReply = 6

# Message flags
MessageFlagsRelayed = 1<<0          # Repeated message
MessageFlagsPleaseRelay = 1<<1      # Please repeat this message

# The message object represents a FreakWAN message, and is also responsible
# of the decoding and encoding of the messages to be sent to the "wire".
class Message:
    def __init__(self, nick="", text="", uid=False, ttl=15, mtype=MessageTypeData, sender=False, flags=0, rssi=0, ack_type=0, seen=0):
        self.ctime = time.ticks_ms() # To evict old messages

        # send_time is only useful for sending, to introduce a random delay.
        self.send_time = self.ctime

        # Number of times to transmit this message. Each time the message
        # is transmitted, this value is reduced by one. When it reaches
        # zero, the message is removed from the send queue.
        self.num_tx = 1
        self.acks = 0       # Number of received ACKs for this message
        self.type = mtype
        self.flags = flags
        self.nick = nick
        self.text = text
        self.uid = uid if uid != False else self.gen_uid()
        self.sender = sender if sender != False else self.get_this_sender()
        self.ttl = ttl              # Only DATA
        self.ack_type = ack_type    # Only ACK
        self.seen = seen            # Only HELLO
        self.rssi = rssi

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
    def encode(self):
        if self.type == MessageTypeData:
            return struct.pack("<BBLB",self.type,self.flags,self.uid,self.ttl)+self.sender+self.nick+":"+self.text
        elif self.type == MessageTypeAck:
            return struct.pack("<BBLB",self.type,self.flags,self.uid,self.ack_type)+self.sender
        elif self.type == MessageTypeHello:
            return struct.pack("<BB6sB",self.type,self.flags,self.sender,self.seen)+self.nick+":"+self.text

    # Fill the message with the data found in the binary representation
    # provided in 'msg'.
    def decode(self,msg):
        try:
            mtype = struct.unpack("<B",msg)[0]
            if mtype == MessageTypeData:
                self.type,self.flags,self.uid,self.ttl,self.sender = struct.unpack("<BBLB6s",msg)
                self.nick,self.text = msg[13:].decode("utf-8").split(":")
                return True
            elif mtype == MessageTypeAck:
                self.type,self.flags,self.uid,self.ack_type,self.sender = struct.unpack("<BBLB6s",msg)
                return True
            elif mtype == MessageTypeHello:
                self.type,self.flags,self.sender,self.seen = struct.unpack("<BB6sB",msg)
                self.nick,self.text = msg[9:].decode("utf-8").split(":")
                return True
            else:
                return False
        except Exception as e:
            print("msg decode error "+str(e))
            return False

    # Create a message object from the binary representation of a message.
    def from_encoded(encoded):
        m = Message()
        if m.decode(encoded):
            return m
        else:
            return False

