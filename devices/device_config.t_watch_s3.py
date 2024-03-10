### Hardware configuration for the Lilygo T-WATCH S3

from axp2101 import AXP2101
from machine import Pin

class DeviceConfig:
    config = {}

    config['st7789'] = {
        'spi_channel': 1,
        'polarity': 1,
        'phase': 1,
        'xstart': 0,
        'ystart': 40,
        'sck': 18,
        'mosi': 13,
        'miso': 37,
        'reset': False,
        'dc': 38,
        'cs': 12,

        'xres': 240,
        'yres': 240,
        'landscape': False,
        'mirror_y': True,
        'mirror_x': True,
        'inversion': True
    }

    # AXP2101 PMU. In the T-WATCH S3 this chip handles the different
    # chips voltage, battery charging and so forth.
    def power_up(freakwan):
        DeviceConfig.axp2101 = AXP2101(sda=10, scl=11)
        # That's too complex to stay inside a configuration, so
        # we have a method in the AXP2101 class.
        DeviceConfig.axp2101.twatch_s3_poweron()
        bl = Pin(45,Pin.OUT)
        bl.on() # Display backlight on.

    def get_battery_microvolts():
        return DeviceConfig.axp2101.get_battery_voltage()*1000

    # Pin configuration for the SX1262.
    config['sx1262'] = {
        'busy': 7,
        'miso': 4,
        'mosi': 1,
        'clock': 3,
        'chipselect': 5,
        'reset': 8,
        'dio': 9,
    }
