# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

from font4x6 import *
from fci import ImageFCI

# This class implements an IRC-alike view for the ssd1306 display.
# it is possible to push new lines of text, and only the latest N will
# be shown, handling also text wrapping if a line is longer than
# the screen width.
class Scroller:
    Font8x8 = 0
    Font4x6 = 1

    def __init__(self, display, get_batt_perc):
        self.display = display  # Display driver
        self.lines = []
        self.xres = 128
        self.yres = 64
        self.get_batt_perc = get_batt_perc # Method to get battery percentage
        # The framebuffer of MicroPython only supports 8x8 fonts so far, so:
        self.select_font("big")

    def select_font(self,fontname):
        if fontname == "big":
            self.font = self.Font8x8
            self.font_width = 8
            self.font_height = 8
        elif fontname == "small":
            # Use 5/7 to provide the required spacing. The font 8x8
            # already includes spacing.
            self.font = self.Font4x6
            self.font_width = 5
            self.font_height = 7
        self.cols = int(self.xres/self.font_width)
        self.rows = int(self.yres/self.font_height)

    def render_text(self,text,x,y,color):
        if self.font == self.Font8x8:
            self.display.text(text, x, y, color)
        else:
            for c in text:
                self.render_4x6_char(c, x, y, color)
                x += self.font_width

    def render_4x6_char(self,c,px,py,color):
        idx = ord(c)
        if idx > len(FontData4x6)/3:
            idx = ord("?")
        for y in range(0,6):
            bits = FontData4x6[idx*3+(int(y/2))]
            if not y & 1: bits >>= 4
            for x in range(0,4):
                if bits & (1<<(3-x)):
                    self.display.pixel(px+x,py+y,color)

    # Return the number of rows needed to display the current self.lines
    # This number may be > self.rows.
    def rows_needed(self):
        needed = 0
        for l in self.lines:
            if isinstance(l,ImageFCI):
                needed += int(self.get_image_padded_height(l.height)/self.font_height)
            else:
                needed += int((len(l)+(self.cols-1))/self.cols)
        return needed

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

    # When displaying images, we need to start from the row edge in order
    # make mixes of images and text well aligned. So we pad the image
    # height to the font height.
    def get_image_padded_height(self,height):
        if height % self.font_height:
            padded_height = height+(self.font_height-(height%self.font_height))
        else:
            padded_height = height
        return padded_height

    # Update the screen content.
    def refresh(self):
        if not self.display: return
        self.display.fill(0)
        # We need to draw the lines backward starting from the last
        # row and going backward. This makes handling line wraps simpler,
        # as we consume from the end of the last line and so forth.
        y = (min(self.rows,self.rows_needed())-1) * self.font_height
        lines = self.lines[:]
        while y >= 0:
            # Handle FCI images
            if isinstance(lines[-1],ImageFCI):
                img = lines[-1]
                lines.pop(-1)
                y -= self.get_image_padded_height(img.height)
                y += self.font_height
                img.draw_into(self.display,0,y)
                y -= self.font_height
                continue

            # Handle text
            if len(lines[-1]) == 0:
                # We consumed all the current line. Remove it
                # and start again from the top of the loop, since
                # the next line could be an image.
                lines.pop(-1)
                if len(lines) == 0: return # Should not happen
                continue

            to_consume = len(lines[-1]) % self.cols
            if to_consume == 0: to_consume = self.cols
            rowchars = lines[-1][-to_consume:] # Part to display from the end
            lines[-1]=lines[-1][:-to_consume]  # Remaining part.
            self.render_text(rowchars, 0, y, 1)
            y -= self.font_height
        self.draw_battery()
        self.display.show()

    # Convert certain unicode points to our 4x6 font characters.
    def convert_from_utf8(self,msg):
        msg = msg.replace("è","\x80")
        msg = msg.replace("é","\x81")
        msg = msg.replace("😀","\x96\x97")
        return msg

    # Add a new line, without refreshing the display.
    def print(self,msg):
        if isinstance(msg,str):
            msg = self.convert_from_utf8(msg)
        self.lines.append(msg)
        self.lines = self.lines[-self.rows:]

