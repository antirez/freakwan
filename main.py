# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import uasyncio as asyncio
from freakwan import FreakWAN

fw = FreakWAN()

# Connect to WiFi ASAP if the configuration demands so.
wifi_network = fw.config.get('wifi_default_network')
if wifi_network:
    fw.start_wifi(wifi_network, fw.config['wifi'][wifi_network])

# All the FreakWAN execution is performed in the 'run' loop, and
# in the callbacks registered during the initialization.
asyncio.create_task(fw.cron())
asyncio.create_task(fw.send_hello_message())
asyncio.create_task(fw.send_periodic_message())
asyncio.create_task(fw.receive_from_serial())
if fw.config.get('irc') and fw.config['irc']['enabled']: fw.start_irc()
if fw.config.get('telegram') and fw.config['telegram']['enabled']: fw.start_telegram()
if fw.bleuart: fw.bleuart.set_callback(fw.ble_receive_callback)

loop = asyncio.get_event_loop()
loop.set_exception_handler(fw.crash_handler)
try:
    loop.run_forever()
except KeyboardInterrupt:
    fw.scroller.print("")
    fw.scroller.print("--- Stopped ---")
    fw.scroller.refresh()
    fw.lora.reset() # Avoid receiving messages while stopped
