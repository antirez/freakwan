import asyncio
from config import Config
from freakwan import FreakWAN
from scroller import Scroller
from web_server import WebServer

async def handle_server_toggle(scroller, server):
    server_task = asyncio.create_task(server.toggle_server())
    await asyncio.gather(server_task)

async def main():
    print("Starting Main")
    # The Config class is used to read and update the configuration file.
    cfg = Config('config.yaml')

    # The WebServer is used to modify the configuration via a web interface.
    ws_ssid = cfg.get_plain()['ap']['ssid']
    ws_pw = cfg.get_plain()['ap']['pw']
    print("Creating WebServer")
    ws = WebServer(ws_ssid, ws_pw, cfg.get, cfg.web_update)

    # The Scroller class is used to display the configuration on the OLED display.
    scroller = Scroller(ws.get_info)
    print("Creating Scroller task")
    asyncio.create_task(scroller.run())

    # The FreakWAN class is the main class that implements networking.
    print("Creating FreakWAN")
    fw = FreakWAN(cfg.get_plain(), cfg.set_update_callback)
    print("Creating FreakWAN tasks")
    asyncio.create_task(fw.cron())
    asyncio.create_task(fw.send_hello_message())
    asyncio.create_task(fw.send_periodic_message())
    asyncio.create_task(fw.receive_from_serial())

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(fw.crash_handler)

    try:
        print("Entering main loop")
        while True:
            for button in [scroller.A, scroller.B, scroller.X, scroller.Y]:
                if scroller.display.scroll.is_pressed(button):
                    scroller.scrolling = True # set interrupt flag
                    scroller.display.clear()
                    # wait for the interrupt check in scroll_text before
                    # resetting flag and starting a new scroll.
                    await handle_server_toggle(scroller, ws)
                await asyncio.sleep_ms(100)
    except KeyboardInterrupt:
        fw.lora.reset() # Avoid receiving messages while stopped

if __name__ == '__main__':
    asyncio.run(main())


