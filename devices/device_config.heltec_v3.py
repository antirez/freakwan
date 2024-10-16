### Heltec V3 hardware configuration

from machine import Pin, ADC
import time

class DeviceConfig:
    config = {}

    config['ssd1306']= {
        'sda': 17,
        'scl': 18,
        'rst': 21,
        'xres': 128,
        'yres': 64,
    }

    config['vext_ctrl'] = {
        'pin': 36
    }

    def power_up(freakwan):
        # Init battery voltage pin
        DeviceConfig.adc_ctrl = Pin(37, Pin.OUT) # on heltec v3 we need to switch a mosfet
        # which gate is on pin 37 to be able to read battery voltage
        DeviceConfig.adc_ctrl.on() # make sure pin is in high state when we are not reading
        DeviceConfig.battery_adc = ADC(Pin(1))

        DeviceConfig.battery_adc.atten(ADC.ATTN_2_5DB)

        # Bind the button present on the board. It is connected to
        # Pin 0, and goes low when pressed.
        button0 = Pin(0,Pin.IN)
        button0.irq(freakwan.button_0_pressed,Pin.IRQ_FALLING)
        DeviceConfig.vext_ctrl = Pin(DeviceConfig.config['vext_ctrl']['pin'], Pin.OUT) # on heltec v3 there's another mosfet to enable power to OLED
        # and possibile external devices, we need to pull this pin low to let current flow
        DeviceConfig.vext_ctrl.off()
        oled_rst = Pin(DeviceConfig.config['ssd1306']['rst'], Pin.OUT)
        oled_rst.off()
        time.sleep_ms(50)
        oled_rst.on()
        time.sleep_ms(50)


    def get_battery_microvolts():
        DeviceConfig.adc_ctrl.off() # switch mosfet low to read battery voltage
        battery_uv = DeviceConfig.battery_adc.read_uv()*4.9 # 390k - 100k voltage divider,
        # this value SHOULD be manually calibrated for your board to accomodate tolerances
        # we should also think on an efficient way to average out values and eliminate outliers
        DeviceConfig.adc_ctrl.on()

        return battery_uv

    config['tx_led'] = {
        'pin': 35,
        'inverted': False,      # Set to True if pin on = led off
    }

    # Pin configuration for the SX1262.
    config['sx1262'] = {
        'busy': 13,
        'miso': 11,
        'mosi': 10,
        'clock': 9,
        'chipselect': 8,
        'reset': 12,
        'dio': 14,
    }
