### This file holds your device hardware configuration.
#
# Here we show a couple of different examples, however if you want
# to create a configuration for your device that is yet not supported
# by FreakWAN, it is probably better to start from the configuration of
# a device similar and modify it.

from machine import Pin

class DeviceConfig:
    config = {}

    ########################### DISPLAY CONFIGURATION ######################

    # Pin configuration for the SSD1306 display.
    # Note: for headless setups without a screen just
    # don't specify any display at all.
    if False:
        config['ssd1306']= {
            'sda': 21,
            'scl': 22,
            'xres': 128,
            'yres': 64,
        }

    if False:
        config['st7789'] = {
            'spi_channel': 1,
            'sck': 18,
            'mosi': 13,
            'miso': 37,
            'reset': False,
            'dc': 38,
            'cs': 12,
            'xres': 240,
            'yres': 240,
        }

    ########################### PMU CONFIGURATION ##########################

    # If the device don't have any way to do it, just return 0,
    # otherwise this method will be override by some next
    # definition.
    def get_battery_microvolts(): return 0
    def power_up(freakwan): pass # By default, nothing to do at power-up.

    # Pin configuration for the AXP192. This PMU chip is found
    # in devices like the T-BEAM, however it is not essential
    # if not to get the battery charge level.
    if False:
        from axp192 import AXP192
        from machine import SoftI2C

        def power_up():
            i2c = SoftI2C(sda=Pin(21), scl=Pin(22))
            DeviceConfig.axp192 = AXP192(i2c)

        def get_battery_microvolts():
            return DeviceConfig.axp192.get_battery_volts()*1000000

    # AXP2101 PMU. In the T-WATCH S3 this chip handles the different
    # chips voltage, battery charging and so forth.
    if False:
        from axp2101 import AXP2101

        def power_up():
            DeviceConfig.axp2101 = AXP2101(sda=10, scl=11)
            # That's too complex to stay inside a configuration, so
            # we have a method in the AXP2101 class.
            DeviceConfig.axp2101.twatch_s3_poweron()

        def get_battery_microvolts():
            return DeviceConfig.axp2101.get_battery_voltage()*1000

    # There are devices, like the T3, where the battery information
    # is obtained just reading an ADC pin.
    if False:
        def power_up():
            # Init battery voltage pin
            DeviceConfig.battery_adc = ADC(Pin(35))

            # Voltage is divided by 2 befor reaching PID 32. Since normally
            # a 3.7V battery is used, to sample it we need the full 3.3
            # volts range.
            DeviceConfig.battery_adc.atten(ADC.ATTN_11DB)

        def get_battery_microvolts():
            return DeviceConfig.battery_adc.read_uv()*2

    ################################# TX LED ###############################

    if False:
        config['tx_led'] = {
            'pin': 25,
            'inverted': False,      # Set to True if pin on = led off
        }

    ########################### LORA CONFIGURATION #########################

    # Pin configuration for the SX1276.
    if False:
        config['sx1276'] = {
            'miso': 19,
            'mosi': 27,
            'clock': 5,
            'chipselect': 18,
            'reset': 23,
            'dio0': 26
        }

    # Pin configuration for the SX1262.
    if False:
        config['sx1262'] = {
            'busy': 7,
            'miso': 4,
            'mosi': 1,
            'clock': 3,
            'chipselect': 5,
            'reset': 8,
            'dio': 9,
        }

    ########################### SENSOR CONFIGURATION #######################
    #
    # This is a special configuration for sensor mode, a yet experimental
    # feature.

    if False:
        config['sensor'] = {
            'type': 'DHT22',
            'dht_pin': 25,
            'period': 30000, # In milliseconds
            'key_name': "sensor_key", # Encryption key for sensor data
            'key_secret': "123456",
        }

