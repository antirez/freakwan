# SX1276 driver for MicroPython
# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This is an example usage, written or the LYLIGO TTGO LoRa ESP32 board.

import ssd1306, sx1276, time, urandom
from machine import Pin, SoftI2C

def receive_callback(lora_instance,packet,RSSI):
    display.fill(0)
    display.text(packet, 0, 0, 1)
    display.text(str(RSSI), 0, 15, 1)
    display.show()

def example():
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
    display = ssd1306.SSD1306_I2C(128, 64, i2c)
    display.poweron()
    display.text('Receiving...', 0, 0, 1)
    display.show()

    lora = sx1276.SX1276(LYLIGO_216_pinconfig,receive_callback)
    lora.begin()
    lora.configure(869500000,500000,8,12)

    if False:
        lora.receive()
    else:
        while True:
            payload = "Test "+str(urandom.randint(0,1000000))
            display.fill(0)
            display.text(payload, 0, 0, 1)
            display.show()
            lora.send(payload)
            time.sleep(5) 

example()
