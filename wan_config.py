class UserConfig:
    config = {}
    # This is just your nickname, how the network will know you.
    # If not set, a fixed one from the device mac address is
    # generated.
    #
    # config['nick']="mynickname"

    # This is a status message sent using HELLO packets, to make
    # others aware of our presence. Other folks will see this message
    # when listing active nodes.
    config['status']="Hi There!"

    # LoRa configuration
    config['lora_sp']=12            # Spreading
    config['lora_bw']=250000        # Bandwidth
    config['lora_cr']=8             # Coding rate
    config['lora_fr']=869500000     # Frequency

    # Pin configuration for the SSD1306 display.
    config['ssd1306']= {
        'sda_pin': 21,
        'scl_pin': 22
    }

    # For headless display, set it to None
    # config['ssd1306'] = None

    # Pin configuration for the SX1276.
    config['sx1276'] = {
        'miso': 19,
        'mosi': 27,
        'clock': 5,
        'chipselect': 18,
        'reset': 23,
        'dio0': 26
    }

    # Pin configuration for the TX led. If missing, set it to None.
    # config ['tx_led'] = None
    config['tx_led'] = {
        'pin': 25,
        'inverted': False,      # Set to True if pin on = led off
    }

    # Goes to deep sleep when this percentage is reached, in order to
    # avoid damaging the battery.
    config['sleep_battery_perc'] = 20
