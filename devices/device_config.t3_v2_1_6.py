### LILYGO T3 v2 1.6 hardware configuration

from machine import Pin, ADC

class DeviceConfig:
    config = {}

    config['ssd1306']= {
        'sda': 21,
        'scl': 22,
        'xres': 128,
        'yres': 64,
    }

    def power_up(freakwan):
        # Init battery voltage pin
        DeviceConfig.battery_adc = ADC(Pin(35))

        # Voltage is divided by 2 befor reaching PID 32. Since normally
        # a 3.7V battery is used, to sample it we need the full 3.3
        # volts range.
        DeviceConfig.battery_adc.atten(ADC.ATTN_11DB)

    def get_battery_microvolts():
        return DeviceConfig.battery_adc.read_uv()*2

    config['tx_led'] = {
        'pin': 25,
        'inverted': False,      # Set to True if pin on = led off
    }

    config['sx1276'] = {
        'miso': 19,
        'mosi': 27,
        'clock': 5,
        'chipselect': 18,
        'reset': 23,
        'dio0': 26
    }
