# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

import math

# This class implements the view that shows the splash screen on startup.
class SplashScreen:
    def __init__(self, display, xres, yres):
        self.display = display  # Display driver
        self.xres = xres
        self.yres = yres
        self.anim_frame = 0     # Animation frame to show

    def next_frame(self):
        self.anim_frame += 1

    def draw_logo(self):
        self.display.fill(0)
        for x in range(0,self.xres,2):
            for y in range(0,self.yres+8,8):
                f1 = self.anim_frame/5
                dy = math.sin(f1+x/(1+(y*17%11)))*4
                self.display.pixel(int(x),y+int(dy),1)
        dx = 15
        dy = 8 
        self.display.fill_rect(dx+0,dy+0,40,10,0);
        self.display.fill_rect(dx+0,dy+20,40,10,0);
        self.display.fill_rect(dx+0,dy+0,10,50,0);
        self.display.line(dx+0,dy+0,dx+0,dy+50,1)
        self.display.line(dx+0,dy+0,dx+30,dy+0,1)
        self.display.line(dx+10,dy+20,dx+30,dy+20,1)
        dx = 55
        dy = 8
        for x in range(10):
            self.display.line(dx+x+0,dy+0,dx+x+15,dy+50,0)
            self.display.line(dx+x+30,dy+0,dx+x+15+30,dy+50,0)
            self.display.line(dx+x+25,dy+0,dx+x+10,dy+50,0)
            self.display.line(dx+x+55,dy+0,dx+x+40,dy+50,0)
        self.display.line(dx,dy,dx+15,dy+50,1)
        self.display.line(dx+30,dy,dx+45,dy+50,1)

    def refresh(self):
        if not self.display: return
        self.draw_logo()
        self.display.show()

# Only useful in order to test the animation quickly in the SD1306
if __name__ == "__main__":
    import ssd1306, time
    from machine import Pin, SoftI2C
    i2c = SoftI2C(sda=Pin(21),scl=Pin(22))
    display = ssd1306.SSD1306_I2C(128, 64, i2c)
    display.poweron()
    splash = SplashScreen(display,128,64)
    for i in range(30):
        splash.refresh()
        splash.next_frame()
        time.sleep_ms(10)
