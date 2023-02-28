# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

from font4x6 import *
import time, urandom

# This class shows status icons on the display. It is called every
# time the current view is refreshed, at the end, so it should assume
# that a view was already drawn and should only operate on the pixels
# related to the icons.
class StatusIcons:
    def __init__(self, display, get_batt_perc):
        self.display = display
        self.xres = 128
        self.yres = 64
        self.get_batt_perc = get_batt_perc # Method to get battery percentage
        self.last_batt_perc = 0
        self.show = {}
        self.show['ack'] = False           # Show ACK received icon if !False
        self.show['relay'] = False         # Show packet relayed icon !False
        self.icons_ttl = 5                 # Turn icons off after N seconds

    # Set to True / False to show/hide ACK icon.
    def set_ack_visibility(self,new):
        self.show['ack'] = time.time() if new else False

    # Set to True / False to show/hide relay icon.
    def set_relay_visibility(self,new):
        self.show['relay'] = time.time() if new else False

    # Display the battery icon, that is built on the
    # following model. There are a total of 10 pixels to
    # fill, so each horizontal pixel is 10% of battery.
    #..............
    #.##########...
    #.#xxxxxxxxx##.
    #.#xxxxxxxxxx#.
    #.#xxxxxxxxx##.
    #.##########...
    #..............
    def draw_battery(self):
        self.last_batt_perc = self.get_batt_perc()
        px = self.xres-14+self.xoff
        py = 0+self.yoff
        self.display.fill_rect(0+px,0+py,14,7,0)
        self.display.fill_rect(1+px,1+py,12,5,1)
        self.display.pixel(11+px,1+py,0)
        self.display.pixel(12+px,1+py,0)
        self.display.pixel(11+px,5+py,0)
        self.display.pixel(12+px,5+py,0)
        self.display.pixel(11+px,3+py,0)
        self.display.fill_rect(2+px,2+py,9,3,0)
        full_pixel = round(self.last_batt_perc/10)
        self.display.fill_rect(2+px,2+py,full_pixel,3,1)

    def draw_ack_icon(self):
        px = self.xres-8+self.xoff
        py = 10+self.yoff
        self.display.fill_rect(px,py,8,9,1)
        self.display.text("A",px,py+1,0)

    def draw_relay_icon(self):
        px = self.xres-8+self.xoff
        py = 22+self.yoff
        self.display.fill_rect(px,py,8,9,1)
        self.display.text("R",px,py+1,0)

    # Return the minimum refresh time of the status icons
    # in seconds, depending on what is enabled right now:
    def min_refresh_time(self):
        # If at least a status icon is enabled right now, better
        # to refresh the display every second.
        for icon in self.show:
            if self.show[icon]: return 1

        # If it's just the battery, it is unlikely that it
        # changes much before one minute.
        return 60

    # Update the screen content. If 'random_offset' is True, we are in
    # screensaver mode and the icons should be displayed at random locations.
    def refresh(self,random_offset=False):
        if not self.display: return
        if random_offset:
            self.xoff = urandom.randint(-(self.xres-10),0)
            self.yoff = urandom.randint(0,self.yres-20)
        else:
            self.xoff = 0
            self.yoff = 0
        self.draw_battery()
        # Turn off icons that timed out.
        for icon in self.show:
            if self.show[icon]:
                age = time.time() - self.show[icon]
                if age > self.icons_ttl: self.show[icon] = False
        if self.show['ack']: self.draw_ack_icon()
        if self.show['relay']: self.draw_relay_icon()
        self.display.show()

# Test code
if __name__ == "__main__":
    import ssd1306, time
    from machine import Pin, SoftI2C

    def get_batt_perc_test():
        return 100

    i2c = SoftI2C(sda=Pin(21),scl=Pin(22))
    display = ssd1306.SSD1306_I2C(128, 64, i2c)
    display.poweron()
    icons = StatusIcons(display,get_batt_perc=get_batt_perc_test)
    icons.set_ack_visibility(True)
    icons.set_relay_visibility(True)
    icons.refresh()
