### LILYGO T3 v2 1.6 hardware configuration

from machine import Pin, ADC

class DeviceConfig:
    config = {}

    config['ssd1306']= {
        'sda': 18,
        'scl': 17,
        'xres': 128,
        'yres': 64,
    }

    def power_up():
        # Init battery voltage pin
        DeviceConfig.battery_adc = ADC(Pin(1))

        # Voltage is divided by 2 befor reaching PID 1. Since normally
        # a 3.7V battery is used, to sample it we need the full 3.3
        # volts range.
        DeviceConfig.battery_adc.atten(ADC.ATTN_11DB)

    def get_battery_microvolts():
        return DeviceConfig.battery_adc.read_uv()*2

    config['tx_led'] = {
        'pin': 37,
        'inverted': False,      # Set to True if pin on = led off
    }

    # Pin configuration for the SX1262.
    config['sx1262'] = {
        'busy': 34,
        'miso': 3,
        'mosi': 6,
        'clock': 5,
        'chipselect': 7,
        'reset': 8,
        'dio': 33,
    }
