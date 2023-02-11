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
