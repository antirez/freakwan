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
    # For headless display, set it to None
    config['ssd1306']= {
        'sda_pin': 21,
        'scl_pin': 22
    }

    # Pin configuration for the SX1276.
    config['sx1276'] = {
        'miso': 19,
        'mosi': 27,
        'clock': 5,
        'chipselect': 18,
        'reset': 23,
        'dio0': 26
    }
