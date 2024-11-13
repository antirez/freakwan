import time
import asyncio
from picoscroll import PicoScroll, WIDTH, HEIGHT


class ScrollDisplay:
    def __init__(self):
        self.scroll = PicoScroll()
        self.DEF_BRIGHTNESS = 10
        self.DEF_SCROLL_DELAY = 60
        self.DEF_LOOP_DELAY = 5000
        
        
    def clear(self):
        self.scroll.clear()
        self.scroll.show()
        

class Scroller:
    def __init__(self, get_server_info):
        self.display = ScrollDisplay()
        self.get_server_info = get_server_info
        self.scrolling = False
        self.A = self.display.scroll.BUTTON_A
        self.B = self.display.scroll.BUTTON_B
        self.X = self.display.scroll.BUTTON_X
        self.Y = self.display.scroll.BUTTON_Y
    
    # TODO: accept callback functions as arguments for button presses.
    
    async def scroll_text(self, text, brightness, delay_ms):
        l = len(text) * 6
        self.scrolling = True
        
        for j in range(-WIDTH, l):
            self.display.scroll.show_text(text, brightness, j)
            self.display.scroll.show()
            await asyncio.sleep_ms(delay_ms)
            
        self.scrolling = False
        return True


    async def show_ap_info(self, brightness, delay_ms):
        self.display.clear()
        server_info = self.get_server_info()
        if server_info.active:
            await self.scroll_text(f'SSID:{server_info.ssid}', brightness, delay_ms)
        else:
            await self.scroll_text('AP:off', brightness, delay_ms)
        
    
    async def show_battery_info(self, level, brightness, delay_ms):
    # TODO: Get actual battery level 
        self.display.clear()
        await self.scroll_text(f'BAT:{level}%', brightness, delay_ms)
      

    async def show_nearby_info(self, nearby, brightness, delay_ms):
    # TODO: Get actual num of neighbours
        self.display.clear()
        await self.scroll_text(f'NEAR:{nearby}', brightness, delay_ms)
     

    async def show_storage_info(self, storage, brightness, delay_ms):
    # TODO: Get actual remaining storage capacity
        self.display.clear()
        await self.scroll_text(f'SD:{storage}%', brightness, delay_ms)  
   

    async def show_rssi_info(self, values, brightness):
        self.display.clear()
        # TODO: Work out what the shape of RSSI data will be, show some chart of strength/time
        # Divide screen into 2pixel columns, column height represents signal strength.
        bar_width = 2
        norm_values = self.normalise_rssi_heights(values)

        for i, height in enumerate(norm_values):
            x_pos = i * bar_width
            
            # Draw the bar using 2 pixel width
            for x in range(x_pos, min(x_pos + bar_width, WIDTH)):
                # Draw pixels from bottom up
                for y in range(HEIGHT - 1, HEIGHT - height - 1, -1):
                    if y >= 0:  # Ensure we don't draw outside bounds
                        self.display.scroll.set_pixel(x, y, brightness)
                    
        self.display.scroll.show()
        await asyncio.sleep_ms(5000)
        return
    

    def normalise_rssi_heights(self, rssi_values):
        normalised = []
        for value in rssi_values:
            normalised.append(min(7, max(0, int((value + 100) * 7 / 100))))
        return normalised


    async def wait_if_interrupted(self):
    # waits for interrupting messages to scroll before continuing.
        while self.scrolling: await asyncio.sleep_ms(1000)


    async def cycle_info(self, loop_delay_ms):
        while True:
            self.wait_if_interrupted()   
            await self.show_battery_info('69', self.display.DEF_BRIGHTNESS, self.display.DEF_SCROLL_DELAY)
            
            self.wait_if_interrupted()
            await self.show_ap_info(self.display.DEF_BRIGHTNESS, self.display.DEF_SCROLL_DELAY)
            
            self.wait_if_interrupted()
            await self.show_nearby_info('2', self.display.DEF_BRIGHTNESS, self.display.DEF_SCROLL_DELAY)
            
            self.wait_if_interrupted()
            await self.show_storage_info('90', self.display.DEF_BRIGHTNESS, self.display.DEF_SCROLL_DELAY)
            
            self.wait_if_interrupted()
            values = [-70, -80, -70, -60, -50, -40, -50, -60]
            await self.show_rssi_info(values, self.display.DEF_BRIGHTNESS)

            # wait longer between loops for battery saving.
            await asyncio.sleep_ms(loop_delay_ms)
            
    async def run(self):
        asyncio.create_task(self.cycle_info(self.display.DEF_LOOP_DELAY))

    