# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

class ImageFCI:
    # Create an image object from data bytes or loading it from
    # a file.
    def __init__(self,data=None,filename=None):
        if data == None:
            if filename == None: raise Exception('No data nor filename given.')
            f = open(filename,'rb')
            data = f.read()
            f.close()

        if data[0:3] != b'FC0':
            raise Exception("FCI Image magic not found")
        self.encoded = data 
        self.width = data[3]
        self.height = data[4]

    def size(self):
        return self.width,self.height

    # Helper of draw_into. Will paint N consecutive pixels of the
    # image set to 'color', from the current position rx,ry.
    def draw_run(self,display,color,runlen):
        while runlen:
            max_line_len = self.width - self.rx
            line_len = min(max_line_len,runlen)
            if color and self.y+self.ry >= 0 and self.y+self.ry < display.height:
                display.line(self.x+self.rx,self.y+self.ry,self.x+self.rx+line_len-1,self.y+self.ry,color)
            self.rx += line_len
            if self.rx == self.width:
                self.rx = 0
                self.ry += 1
            runlen -= line_len

    # Helper of draw_into. Will draw the pixels of "byte"
    # into the image, starting from the current position rx,ry.
    def draw_verb(self,display,pattern):
        for bit in range(7,-1,-1):
            if pattern & (1<<bit) and self.y+self.ry >= 0 and self.y+self.ry < display.height:
                display.pixel(self.x+self.rx,self.y+self.ry,1)
            self.rx += 1
            if self.rx == self.width:
                self.rx = 0
                self.ry += 1
            if self.ry == self.height: break

    # Decode and draw the image into the canvas in one pass.
    # The ESP32 is CPU-capable and memory-constrained, so this is
    # a sensible approach to avoid going out of memory.
    #
    # The 'display' object should implement the MicroPython
    # framebuffer interface. We use only a few methods in total.
    #
    # Note: this function will not call display.show(), so if you
    # can't see anything, make sure the caller will actually show
    # the image into the display.
    def draw_into(self,display,x,y):
        display.fill_rect(x,y,self.width,self.height,0)
        self.x,self.y = x,y   # Where to draw the image
        self.rx,self.ry = 0,0 # Next point to draw
        i = 5 # First byte after image header
        opcodes = len(self.encoded)
        while i < opcodes:
            op = self.encoded[i]
            i += 1
            if op == 0xc3 and i != opcodes:
                run = self.encoded[i]
                i += 1
                if run:
                    self.draw_run(display,run>>7,(run&0x7f)+16)
                else:
                    self.draw_verb(display,op)
            elif (op == 0x3d or op == 0x65) and i != opcodes:
                run = self.encoded[i]
                i += 1
                if run:
                    # Bit 4 and 6 of the two opcodes control
                    # if to draw the two small runs white/black
                    # or black/white.
                    self.draw_run(display,(op>>4)&1,((run&0xf0)>>4)+1)
                    self.draw_run(display,(op>>6)&1,(run&0xf)+1)
                else:
                    self.draw_verb(display,op)
            else:
                self.draw_verb(display,op)

if __name__ == "__main__":
    import ssd1306, time
    from machine import Pin, SoftI2C
    i2c = SoftI2C(sda=Pin(21),scl=Pin(22))
    display = ssd1306.SSD1306_I2C(128, 64, i2c)
    display.poweron()
    display.fill(0)
    img = ImageFCI(filename="mammoriano.fci")
    img.draw_into(display,0,0)
    display.show()
