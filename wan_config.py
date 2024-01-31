### IMPORTANT NOTICE
###
### Please, be aware that certain things configured in this file
### can also be configured with bang commands, like !wifi, !irc
### and so forth. After a "!config save" command, the configuration
### saved in "settings.txt" overrides what you define here.

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
    config['lora_pw']=17            # TX power (dbm, range 2-20)

   # WiFi network, in order to use the IRC interface.
    config['wifi'] = {
        'mynetwork1': 'mypassword',
        'ssid2': 'password2'
    }

    # WiFi network to join at startup.
    config['wifi_default_network'] = False

    # IRC configuration. Just if it is enabled or not. The channel name is
    # automatically created from the nick of the device. See README.
    config['irc'] = {
        'enabled': False
    }

    # Goes to deep sleep when this percentage is reached, in order to
    # avoid damaging the battery.
    config['sleep_battery_perc'] = 20
