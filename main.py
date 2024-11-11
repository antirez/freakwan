# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import asyncio
from freakwan import FreakWAN

fw = FreakWAN()

# All the FreakWAN execution is performed in the 'run' loop, and
# in the callbacks registered during the initialization.
asyncio.create_task(fw.cron())
asyncio.create_task(fw.send_hello_message())
asyncio.create_task(fw.send_periodic_message())
asyncio.create_task(fw.receive_from_serial())

loop = asyncio.get_event_loop()
loop.set_exception_handler(fw.crash_handler)
try:
    loop.run_forever()
except KeyboardInterrupt:
    fw.lora.reset() # Avoid receiving messages while stopped
