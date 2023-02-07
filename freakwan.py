# SX1276 driver for MicroPython
# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import machine
import ssd1306, sx1276, time, urandom, struct
from machine import Pin, SoftI2C

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
    def __init__(self, sender, text, uid=False, ttl=3):
        self.sender = sender
        self.text = text
        self.uid = uid if uid != False else self.gen_uid()
        self.ttl = ttl

    def gen_uid(self):
        return urandom.getrandbits(32)

    def encode(self):
        return struct.pack("LB",self.uid,self.ttl)+self.sender+":"+self.text

    def decode(self,msg):
        try:
            self.uid,self.ttl = struct.unpack("LB",msg)
            self.sender,self.text = msg[5:].decode("utf-8").split(":")
            return True
        except Exception as e:
            print(e)
            return False

    def from_encoded(encoded):
        m = Message("_sender_","_txt_")
        m.decode(encoded)
        return m

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
        self.lora.begin()
        self.lora.configure(869500000,500000,8,12)

        # Start receiving. This will just install the IRQ
        # handler, without blocking the program.
        self.lora.receive()

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

    def receive_callback(self,lora_instance,packet,RSSI):
        m = Message.from_encoded(packet)
        self.scroller.print(m.sender+"> "+m.text)
        self.scroller.refresh()

    def run(self):
        counter = 0
        while True:
            msg = Message(sender=self.device_hw_nick(),
                         text="Hi "+str(counter))
            self.lora.send(msg.encode())
            self.scroller.print("you> "+msg.text)
            time.sleep(5) 
            counter += 1

fw = FreakWAN()
fw.run()
