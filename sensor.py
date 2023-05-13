# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import struct
import dht
from machine import Pin
from message import *

# This class is used only when in sensor mode. An object of type sensor
# is created, and later used in the FreakWAN main code path in order to
# get the reading from the sensors, encode and send the information.
class Sensor:
    def __init__(self,fw,sensor_config):
        self.fw = fw
        self.config = sensor_config
        self.state = "send_sample"

        # We don't want any automatic communication when acting as sensors.
        fw.config['quiet'] = True
        fw.config['automsg'] = False

        # Add the sensor channel key if needed.
        if not self.fw.keychain.has_key(self.config['key_name']):
            self.fw.keychain.add_key(self.config['key_name'],self.config['key_secret'])

    # This method is called from FreakWAN main loop in order to
    # execute the sensor state machine, that is: send sample, wait
    # for reply for some time, then go in deep sleep.
    def exec_state_machine(self,tick):
        # Send sensor data. After this step, there should be a pending
        # message in the TX queue, with the encoded readings of the
        # sensor.
        if self.state == "send_sample":
            print("[sensor] sending sample")
            self.send_sample()
            self.state = "wait_tx"

        # Once the TX queue is empty, we will wait a bit more in order
        # to receive some data: then we will shut down and enter
        # in deep sleep.
        if self.state == "wait_tx":
            if len(self.fw.send_queue) == 0:
                print("[sensor] data sent (tx queue is empty)")
                # Give it 10 seconds to receive some reply.
                self.poweroff_tick = tick + 100
                self.state = "wait_poweroff"

        # Finally shut down if we sent the message and the time to
        # receive some command elapsed.
        if self.state == "wait_poweroff":
            if tick == self.poweroff_tick:
                print("[sensor] entering deep sleep")
                self.fw.power_off(self.config['period'])

    def send_sample(self):
        if self.config['type'] == 'DHT22':
            self.send_sample_dht22()

    # This gets a dictionary of sensor data types and readings, and creates
    # the payload for the media message. The format used is just of one
    # byte reading type followed by the information itself (usually encoded
    # as a floating point number, but it is type-specific), so multiple readings
    # are sent in a single message.
    def encode_data(self,data):
        encoded = bytes()
        for keytype in data:
            encoded += struct.pack("<Bf",keytype,data[keytype])
        return encoded

    def send_sample_dht22(self):
        d = dht.DHT22(Pin(self.config['dht_pin']))
        temp = 0
        hum = 0
        numtry = 0

        # Sometimes the DHT22 may return a timeout error.
        # If we run into the error multiple times, send a 0/0
        # reading to notify that the sensor is damaged.
        while numtry < 3 and temp == 0 and hum == 0:
            numtry += 1
            try:
                d.measure()
                temp = d.temperature()
                hum = d.humidity()
            except:
                pass

        data = self.encode_data({
            MessageSensorDataTemperature: temp,
            MessageSensorDataAirHumidity: hum 
        })
        msg = Message(flags=MessageFlagsMedia,nick=self.fw.config['nick'],media_type=MessageMediaTypeSensorData,media_data=data,key_name=self.config['key_name'])
        self.fw.send_asynchronously(msg,max_delay=0,num_tx=1,relay=True)
        self.fw.scroller.print("you> T:%.2f, H:%.2f" % (d.temperature(),d.humidity()))
        self.fw.refresh_view()
