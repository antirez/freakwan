# SX1276 driver for MicroPython
# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import machine
import ssd1306, sx1276, time, urandom, struct
from machine import Pin, SoftI2C
import uasyncio as asyncio

MessageTypeData = 0
MessageTypeAck = 1
MessageTypeHello = 2
MessageTypeBulkStart = 3
MessageTypeBulkData = 4
MessageTypeBulkEND = 5
MessageTypeBulkReply = 6

MessageFlagsRepeat = 1<<0

# This class implements an IRC-alike view for the ssd1306 display.
# it is possible to push new lines of text, and only the latest N will
# be shown, handling also text wrapping if a line is longer than
# the screen width.
class Scroller:
    def __init__(self, display):
        self.display = display # ssd1306 actual driver
        self.lines = []
        self.xres = 128
        self.yres = 64
        self.rows = 8

    # Update the screen content.
    def refresh(self):
        self.display.fill(0)
        for i in range(len(self.lines)):
            self.display.text(self.lines[i], 0, i*8, 1)
        self.display.show()

    # Add a new line, without refreshing the display.
    def print(self,msg):
        self.lines.append(msg)
        self.lines = self.lines[-self.rows:]

# The message object represents a FreakWAN message, and is also responsible
# of the decoding and encoding of the messages to be sent to the "wire".
class Message:
    def __init__(self, nick="", text="", uid=False, ttl=3, mtype=MessageTypeData, sender=False, flags=0, rssi=0, ack_type = 0):
        self.ctime = time.ticks_ms() # To evict old messages

        # send_time is only useful for sending, to introduce a random delay.
        self.send_time = self.ctime

        # Number of times to transmit this message. Each time the message
        # is transmitted, this value is reduced by one. When it reaches
        # zero, the message is removed from the send queue.
        self.num_tx = 1

        self.type = mtype
        self.flags = flags
        self.nick = nick
        self.text = text
        self.uid = uid if uid != False else self.gen_uid()
        self.sender = sender if sender != False else self.get_this_sender()
        self.ttl = ttl
        self.ack_type = ack_type

        self.acks = {} # IDs of devices that acknowledged this message
        self.rssi = rssi

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
            return "%02x%02x%02x%02x%02x%02x" % s[0],s[1],s[2],s[3],s[4],s[5]
        else:
            return "ffffffffffff"

    def encode(self):
        if self.type == MessageTypeData:
            return struct.pack("<BBLB",self.type,self.flags,self.uid,self.ttl)+self.sender+self.nick+":"+self.text
        elif self.type == MessageTypeAck:
            return struct.pack("<BBLB",self.type,self.flags,self.uid,self.ack_type)+self.sender

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
            else:
                return False
        except Exception as e:
            print("msg decode error "+str(e))
            return False

    def from_encoded(encoded):
        m = Message()
        if m.decode(encoded):
            return m
        else:
            return False

class FreakWAN:
    def __init__(self):
        LYLIGO_216_pinconfig = {
            'miso': 19,
            'mosi': 27,
            'clock': 5,
            'chipselect': 18,
            'reset': 23,
            'dio0': 26
        }

        # Init display
        i2c = SoftI2C(sda=Pin(21), scl=Pin(22))
        self.display = ssd1306.SSD1306_I2C(128, 64, i2c)
        self.display.poweron()
        self.display.text('Starting...', 0, 0, 1)
        self.display.show()
        self.scroller = Scroller(self.display)

        # Init LoRa chip
        self.lora = sx1276.SX1276(LYLIGO_216_pinconfig,self.receive_callback)
        self.lora_reset_and_configure()

        # Initialize data structures...

        # Messages we should send ASAP. We append stuff here, so they
        # should be sent in reverse order, from index 0.
        self.send_queue = []
        self.send_queue_max = 100 # Don't accumulate too many messages

        # The 'seen' dictionary contains messages IDs of messages already
        # received/processed. We save the ID and the associated message
        # in case we are the originators (in order to collect acks). The
        # message has also a timestamp, this way we can evict old messages
        # from this list, to avoid a memory usage explosion.
        self.seen = {}

        # Start receiving. This will just install the IRQ
        # handler, without blocking the program.
        self.lora.receive()

    # Reset the chip and configure with the required paramenters.
    # Used during initialization and also in the TX watchdog if
    # the radio is stuck transmitting the current frame for some
    # reason.
    def lora_reset_and_configure(self):
        self.lora.begin()
        self.lora.configure(869500000,500000,8,12)

    # Return a human readable nickname for the device, composed
    # using the device unique ID.
    def device_hw_nick(self):
        uid = list(machine.unique_id())
        nick = ""
        consonants = "kvprmnzflst"
        vowels = "aeiou"
        for x,y in zip(uid[0::2],uid[1::2]):
            nick += consonants[x%len(consonants)]
            nick += vowels [y%len(vowels)]
        return nick

    # Put a packet in the send queue. Will be delivered ASAP.
    # The delay is in milliseconds, and is selected randomly
    # between 0 and the specified amount.
    def send_asynchronously(self,m,max_delay=2000,num_tx=1):
        if len(self.send_queue) >= self.send_queue_max: return False
        m.send_time = time.ticks_add(time.ticks_ms(),urandom.randint(0,max_delay))
        m.num_tx = num_tx
        self.send_queue.append(m)
        return True

    # Send packets waiting in the send queue. This function, right now,
    # will just send every packet in the queue. But later it should
    # implement percentage of channel usage to be able to send only
    # a given percentage of the time.
    def send_messages_in_queue(self):
        send_later = [] # List of messages we can't send, yet.
        while len(self.send_queue):
            m = self.send_queue.pop(0)
            if (time.ticks_diff(time.ticks_ms(),m.send_time) > 0):

                # If the radio is busy sending. We wait here.
                # However it was sperimentally observed that sometimes
                # it can get stuck (maybe because of some race condition
                # in this code?). So if a given amount of time has elapsed
                # without progresses, we reset the radio and return.
                wait_ms_counter = 0
                wait_ms_counter_max = 5000 # 5 seconds
                while(self.lora.tx_in_progress):
                    wait_ms_counter += 1
                    if wait_ms_counter == 5000:
                        print("WARNING: TX watchdog radio reset")
                        self.lora_reset_and_configure()
                        self.lora.receive()
                        return
                    time.sleep_ms(1)
                self.lora.send(m.encode())
                time.sleep_ms(1)
            else:
                send_later.append(m)
        self.send_queue = send_later

    # Called upon reception of some message. It triggers sending an ACK
    # if certain conditions are met. This method does not check the
    # message type: it is assumed that the method is called only for
    # message type where this makes sense.
    def send_ack_if_needed(self,m):
        if m.type != MessageTypeData: return    # Acknowledge only data
        if m.flags & MessageFlagsRepeat: return # Don't acknowledge repeated
        ack = Message(mtype=MessageTypeAck,uid=m.uid,ack_type=m.type,sender=m.sender)
        self.send_asynchronously(ack)
        self.scroller.print(">> ACK sent")

    def receive_callback(self,lora_instance,packet,rssi):
        print("receive_callback()")
        m = Message.from_encoded(packet)
        if m:
            m.rssi = rssi
            if m.type == MessageTypeData:
                self.scroller.print(m.nick+"> "+m.text)
                self.scroller.refresh()
                self.send_ack_if_needed(m)
            elif m.type == MessageTypeAck:
                self.scroller.print(m.nick+"<< ACK received")
                self.scroller.refresh()
            else:
                print("Unknown message type received: "+str(m.type))

    async def send_periodic_message(self):
        counter = 0
        while True:
            msg = Message(nick=self.device_hw_nick(),
                        text="Hi "+str(counter))
            self.send_asynchronously(msg,max_delay=0,num_tx=3)
            self.scroller.print("you> "+msg.text)
            self.scroller.refresh()
            await asyncio.sleep(urandom.randint(3000,5000)/1000) 
            counter += 1

    async def run(self):
        asyncio.create_task(self.send_periodic_message())
        tick = 0
        while True:
            tick += 1
            self.send_messages_in_queue()
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    fw = FreakWAN()
    asyncio.run(fw.run())
