# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

# This class implements the view that shows the splash screen on startup.
class SplashScreen:
    def __init__(self, display):
        self.display = display # ssd1306 actual driver
        self.xres = 128
        self.yres = 64

    def draw_logo(self):
        self.display.fill(0)
        self.display.line(0,0,50,50,1)

    def refresh(self):
        self.draw_logo()
        self.display.show()
