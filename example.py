# SX1276 driver for MicroPython
# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This is an example usage, written or the LYLIGO TTGO LoRa ESP32 board.

import ssd1306, sx1276, time, urandom
from machine import Pin, SoftI2C

class SX1276Example:
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
        self.display.text('Receiving...', 0, 0, 1)
        self.display.show()

        # Init LoRa chip
        self.lora = sx1276.SX1276(LYLIGO_216_pinconfig,self.receive_callback)
        self.lora.begin()
        self.lora.configure(869500000,500000,8,12)

        # Start receiving. This will just install the IRQ
        # handler, without blocking the program.
        self.lora.receive()

    def receive_callback(self,lora_instance,packet,RSSI):
        self.display.fill(0)
        self.display.text(packet, 0, 0, 1)
        self.display.text(str(RSSI), 0, 15, 1)
        self.display.show()

    def run(self):
        # Other than receiving, every 5 seconds send a packet.
        while True:
            payload = "Test "+str(urandom.randint(0,1000000))
            self.display.fill(0)
            self.display.text(payload, 0, 0, 1)
            self.display.show()
            self.lora.send(payload)
            time.sleep(5) 

example = SX1276Example()
example.run()
