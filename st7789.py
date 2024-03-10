# This code is originally from https://github.com/devbis/st7789py_mpy
# It's under the MIT license as well.
#
# Rewritten by Salvatore Sanfilippo.
#
# Copyright (C) 2024 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
# All the changes released under the MIT license as the original code.

import time
from micropython import const
import ustruct as struct
import framebuf

# Commands. We use a small subset of what is
# available and assume no MISO pin to read
# from the display.
ST77XX_NOP = bytes([0x00])
ST77XX_SWRESET = bytes([0x01])
ST77XX_SLPIN = bytes([0x10])
ST77XX_SLPOUT = bytes([0x11])
ST77XX_NORON = bytes([0x13])
ST77XX_INVOFF = bytes([0x20])
ST77XX_INVON = bytes([0x21])
ST77XX_DISPON = bytes([0x29])
ST77XX_CASET = bytes([0x2A])
ST77XX_RASET = bytes([0x2B])
ST77XX_RAMWR = bytes([0x2C])
ST77XX_COLMOD = bytes([0x3A])
ST7789_MADCTL = bytes([0x36])

# MADCTL command flags
ST7789_MADCTL_MY = const(0x80)
ST7789_MADCTL_MX = const(0x40)
ST7789_MADCTL_MV = const(0x20)
ST7789_MADCTL_ML = const(0x10)
ST7789_MADCTL_BGR = const(0x08)
ST7789_MADCTL_MH = const(0x04)
ST7789_MADCTL_RGB = const(0x00)

# COLMOD command flags
ColorMode_65K = const(0x50)
ColorMode_262K = const(0x60)
ColorMode_12bit = const(0x03)
ColorMode_16bit = const(0x05)
ColorMode_18bit = const(0x06)
ColorMode_16M = const(0x07)

# Struct pack formats for pixel/pos encoding
_ENCODE_PIXEL = ">H"
_ENCODE_POS = ">HH"

class ST7789_base:
    def __init__(self, spi, width, height, reset, dc, cs=None):
        """
        display = st7789.ST7789(
            SPI(1, baudrate=40000000, phase=0, polarity=1),
            240, 240,
            reset=machine.Pin(5, machine.Pin.OUT),
            dc=machine.Pin(2, machine.Pin.OUT),
        )

        """
        self.width = width
        self.height = height
        self.spi = spi
        self.reset = reset
        self.dc = dc
        self.cs = cs

        # Always allocate a tiny 8x8 framebuffer in RGB565 for fast
        # single chars plotting. This is useful in order to draw text
        # using the framebuffer 8x8 font inside micropython and using
        # a single SPI write for each whole character.
        self.charfb_data = bytearray(8*8*2)
        self.charfb = framebuf.FrameBuffer(self.charfb_data,8,8,framebuf.RGB565)

    # That's the color format our API takes. We take r, g, b, translate
    # to 16 bit value and pack it as as two bytes.
    def color(self, r=0, g=0, b=0):
        # Convert red, green and blue values (0-255) into a 16-bit 565 encoding.
        c = (r & 0xf8) << 8 | (g & 0xfc) << 3 | b >> 3
        return struct.pack(_ENCODE_PIXEL, c)

    def write(self, command=None, data=None):
        """SPI write to the device: commands and data"""
        if command is not None:
            self.dc.off()
            self.spi.write(command)
        if data is not None:
            self.dc.on()
            if len(data): self.spi.write(data)

    def hard_reset(self):
        if self.reset:
            self.reset.on()
            time.sleep_ms(50)
            self.reset.off()
            time.sleep_ms(50)
            self.reset.on()
            time.sleep_ms(150)

    def soft_reset(self):
        self.write(ST77XX_SWRESET)
        time.sleep_ms(150)

    def sleep_mode(self, value):
        if value:
            self.write(ST77XX_SLPIN)
        else:
            self.write(ST77XX_SLPOUT)

    def inversion_mode(self, value):
        if value:
            self.write(ST77XX_INVON)
        else:
            self.write(ST77XX_INVOFF)

    def _set_color_mode(self, mode):
        self.write(ST77XX_COLMOD, bytes([mode & 0x77]))

    def init(self, landscape=False, mirror_x=False, mirror_y=False, is_bgr=False, xstart = None, ystart = None, inversion = False):

        self.inversion = inversion
        self.mirror_x = mirror_x
        self.mirror_y = mirror_y

        # Configure display parameters that depend on the
        # screen size.
        if xstart != None and ystart != None:
            self.xstart = xstart
            self.ystart = ystart
        elif (self.width, self.height) == (128, 160):
            self.xstart = 0
            self.ystart = 0
        elif (self.width, self.height) == (240, 240):
            self.xstart = 0
            self.ystart = 0
            if self.mirror_y: self.ystart = 40
        elif (self.width, self.height) == (135, 240):
            self.xstart = 52
            self.ystart = 40
        else:
            self.xstart = 0
            self.ystart = 0

        if self.cs:
            self.cs.off() # Take this like that forever, much faster than
                          # continuously setting it on/off and rarely the
                          # SPI is connected to any other hardware.
        self.hard_reset()
        self.soft_reset()
        self.sleep_mode(False)

        color_mode=ColorMode_65K | ColorMode_16bit
        self._set_color_mode(color_mode)
        time.sleep_ms(50)
        self._set_mem_access_mode(landscape, mirror_x, mirror_y, is_bgr)
        self.inversion_mode(self.inversion)
        time.sleep_ms(10)
        self.write(ST77XX_NORON)
        time.sleep_ms(10)
        self.fill(self.color(0,0,0))
        self.write(ST77XX_DISPON)
        time.sleep_ms(500)

    def _set_mem_access_mode(self, landscape, mirror_x, mirror_y, is_bgr):
        value = 0
        if landscape: value |= ST7789_MADCTL_MV
        if mirror_x: value |= ST7789_MADCTL_MX
        if mirror_y: value |= ST7789_MADCTL_MY
        if is_bgr: value |= ST7789_MADCTL_BGR
        self.write(ST7789_MADCTL, bytes([value]))

    def _encode_pos(self, x, y):
        """Encode a postion into bytes."""
        return struct.pack(_ENCODE_POS, x, y)

    def _set_columns(self, start, end):
        self.write(ST77XX_CASET, self._encode_pos(start+self.xstart, end+self.xstart))

    def _set_rows(self, start, end):
        start += self.ystart
        end += self.ystart
        self.write(ST77XX_RASET, self._encode_pos(start+self.ystart, end+self.ystart))

    # Set the video memory windows that will be receive our
    # SPI data writes. Note that this function assumes that
    # x0 <= x1 and y0 <= y1.
    def set_window(self, x0, y0, x1, y1):
        self._set_columns(x0, x1)
        self._set_rows(y0, y1)
        self.write(ST77XX_RAMWR)

    # Drawing raw pixels is a fundamental operation so we go low
    # level avoiding function calls. This and other optimizations
    # made drawing 10k pixels with an ESP2866 from 420ms to 100ms.
    def pixel(self,x,y,color):
        if x < 0 or x >= self.width or y < 0 or y >= self.height: return
        self.dc.off()
        self.spi.write(ST77XX_CASET)
        self.dc.on()
        self.spi.write(self._encode_pos(x+self.xstart, x+self.xstart))

        self.dc.off()
        self.spi.write(ST77XX_RASET)
        self.dc.on()
        self.spi.write(self._encode_pos(y+self.ystart*2, y+self.ystart*2))

        self.dc.off()
        self.spi.write(ST77XX_RAMWR)
        self.dc.on()
        self.spi.write(color)

    # Just fill the whole display memory with the specified color.
    # We use a buffer of screen-width pixels. Even in the worst case
    # of 320 pixels, it's just 640 bytes. Note that writing a scanline
    # per loop dramatically improves performances.
    def fill(self,color):
        self.set_window(0, 0, self.width-1, self.height-1)
        buf = color*self.width
        for i in range(self.height): self.write(None, buf)

    # Draw a full or empty rectangle.
    # x,y are the top-left corner coordinates.
    # w and h are width/height in pixels.
    def rect(self,x,y,w,h,color,fill=False):
        if fill:
            self.set_window(x,y,x+w-1,y+1-w)
            if w*h > 256:
                buf = color*w
                for i in range(h): self.write(None, buf)
            else:
                buf = color*(w*h)
                self.write(None, buf)
        else:
            self.hline(x,x+w-1,y,color)
            self.hline(x,x+w-1,y+h-1,color)
            self.vline(y,y+h-1,x,color)
            self.vline(y,y+h-1,x+w-1,color)

    # We can draw horizontal and vertical lines very fast because
    # we can just set a 1 pixel wide/tall window and fill it.
    def hline(self,x0,x1,y,color):
        if y < 0 or y >= self.height: return
        x0,x1 = max(min(x0,x1),0),min(max(x0,x1),self.width-1)
        self.set_window(x0, y, x1, y)
        self.write(None, color*(x1-x0+1))

    # Same as hline() but for vertical lines.
    def vline(self,y0,y1,x,color):
        y0,y1 = max(min(y0,y1),0),min(max(y0,y1),self.height-1)
        self.set_window(x, y0, x, y1)
        self.write(None, color*(y1-y0+1))

    # Draw a single character 'char' using the font in the MicroPython
    # framebuffer implementation. It is possible to specify the background and
    # foreground color in RGB.
    # Note: in order to uniform this API with all the rest, that takes
    # the color as two bytes, we convert the colors back into a 16 bit
    # rgb565 value since this is the format that the framebuffer
    # implementation expects.
    def char(self,x,y,char,fgcolor,bgcolor):
        if x >= self.width or y >= self.height:
            return # Totally out of display area

        # Obtain the character representation in our
        # 8x8 framebuffer.
        self.charfb.fill(bgcolor[1]<<8|bgcolor[0])
        self.charfb.text(char,0,0,fgcolor[1]<<8|fgcolor[0])

        if x+7 >= self.width:
            # Right side of char does not fit on the screen.
            # Partial update.
            width = self.width-x # Visible width pixels
            self.set_window(x, y, x+width-1, y+7)
            copy = bytearray(width*8*2)
            for dy in range(8):
                src_idx = (dy*8)*2
                dst_idx = (dy*width)*2
                copy[dst_idx:dst_idx+width*2] = self.charfb_data[src_idx:src_idx+width*2]
            self.write(None,copy)
        else:
            self.set_window(x, y, x+7, y+7)
            self.write(None,self.charfb_data)

    # Write text. Like 'char' but for full strings.
    def text(self,x,y,txt,fgcolor,bgcolor):
        for i in range(len(txt)):
            self.char(x+i*8,y,txt[i],fgcolor,bgcolor)

    # Turn on framebuffer. You can write to it directly addressing
    # the fb instance like in:
    #
    # display.fb.fill(display.fb_color(100,50,50))
    # display.show()
    def enable_framebuffer(self,mono=False):
        if mono == False:
            self.fbformat = framebuf.RGB565
            self.rawbuffer = bytearray(self.width*self.height*2)
            self.show = self.show_rgb
        else:
            self.fbformat = framebuf.MONO_HMSB
            self.rawbuffer = bytearray((self.width*self.height+7)//8)
            self.show = self.show_mono

        self.fb = framebuf.FrameBuffer(self.rawbuffer,
            self.width,self.height,self.fbformat)

    # This function is used to conver an RGB value to the
    # equivalent color for the framebuffer functions.
    def fb_color(self,r,g,b):
        c = self.color(r,g,b)
        return c[1]<<8 | c[0]

    # Transfer the framebuffer image into the display. RGB565 mode.
    def show_rgb(self):
        self.set_window(0,0,self.width-1,self.height-1)
        self.write(None, self.rawbuffer)

    # This function uses the Viper native code emitter with a speedup
    # of 20x or alike. It converts rows of 1 bit pixels into a rows
    # of RGB565 pixels, to transfer our mono framebuffer in the display
    # memory. On a Raspberry Pico this takes about ~60ms.
    @micropython.viper
    def fast_mono_to_rgb(self, fb8: ptr8, width: int, height: int):
        # Just allocate one row worth of buffer.
        row = bytearray(int(self.width)*2)
        dst = ptr16(row)
        bit = int(0)
        for y in range(height):
            for x in range(width):
                byte = bit//8
                color = 0xffff * ((fb8[byte] >> (bit&7)) & 1)
                dst[x] = color
                bit += 1
            # Each row is written in a single SPI call.
            self.write(None, row)

    # Transfer the framebuffer image into the display. 1 bit mode, so
    # this requires a conversion while transferring data.
    def show_mono(self):
        self.set_window(0,0,self.width-1,self.height-1)
        self.fast_mono_to_rgb(self.rawbuffer,self.width,self.height)
