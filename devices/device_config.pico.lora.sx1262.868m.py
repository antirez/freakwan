### Raspberry Pi Pico/PICO W with Pico-LoRa-SX1262-868M hat hardware configuration
from machine import ADC, Pin

class DeviceConfig:
    config = {}

    def power_up(freakwan):
        DeviceConfig.battery_adc = ADC(Pin(26))

    config['tx_led'] = {
        'pin': 'WL_GPIO0',
        'inverted': True,
    }

    def get_battery_microvolts():
        # The voltage divider of the hat does not have coupled resistors, 
        # and the theoretical value of 3 needs to be calibrated. 
        # In my case, the value was approximately 3.12
        return (3300000.0/65535.0) * DeviceConfig.battery_adc.read_u16() * 3.12

    # Pin configuration for the SX1262.
    config['sx1262'] = {
        'busy': 2,
        'miso': 12,
        'mosi': 11,
        'clock': 10,
        'chipselect': 3,
        'reset': 15,
        'dio': 20,
    }
 
