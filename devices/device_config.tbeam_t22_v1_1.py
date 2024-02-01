### LILYGO T-BEAM T22 v1.1 hardware configuration

from machine import Pin, SoftI2C
from axp192 import AXP192

class DeviceConfig:
    config = {}

    config['ssd1306']= {
        'sda': 21,
        'scl': 22,
        'xres': 128,
        'yres': 64,
    }

    def power_up():
        i2c = SoftI2C(sda=Pin(21), scl=Pin(22))
        DeviceConfig.axp192 = AXP192(i2c)

    def get_battery_microvolts():
        return DeviceConfig.axp192.get_battery_volts()*1000000

    config['tx_led'] = {
        'pin': 4,
        'inverted': True,
    }

    config['sx1276'] = {
        'miso': 19,
        'mosi': 27,
        'clock': 5,
        'chipselect': 18,
        'reset': 23,
        'dio0': 26
    }
