# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

from font4x6 import *
from fci import ImageFCI

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
        batt_perc = self.get_batt_perc()
        px = self.xres-14
        self.display.fill_rect(0+px,0,14,7,0)
        self.display.fill_rect(1+px,1,12,5,1)
        self.display.pixel(11+px,1,0)
        self.display.pixel(12+px,1,0)
        self.display.pixel(11+px,5,0)
        self.display.pixel(12+px,5,0)
        self.display.pixel(11+px,3,0)
        self.display.fill_rect(2+px,2,9,3,0)
        full_pixel = round(batt_perc/10)
        self.display.fill_rect(2+px,2,full_pixel,3,1)

    # Update the screen content.
    def refresh(self):
        if not self.display: return
        self.draw_battery()
        self.display.show()
