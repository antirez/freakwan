# Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
# All Rights Reserved
#
# This code is released under the BSD 2 clause license.
# See the LICENSE file for more information

# This class implements an IRC-alike view for the ssd1306 display.
# it is possible to push new lines of text, and only the latest N will
# be shown, handling also text wrapping if a line is longer than
# the screen width.
class Scroller:
    def __init__(self, display):
        self.display = display # ssd1306 actual driver
        self.lines = []
        self.xres = 128
        self.yres = 64
        # The framebuffer of MicroPython only supports 8x8 fonts so far, so:
        self.cols = int(self.xres/8)
        self.rows = int(self.yres/8)

    # Return the number of rows needed to display the current self.lines
    # This number may be > self.rows.
    def rows_needed(self):
        needed = 0
        for l in self.lines:
            needed += int((len(l)+(self.cols-1))/self.cols)
        return needed

    # Update the screen content.
    def refresh(self):
        self.display.fill(0)
        # We need to draw the lines backward starting from the last
        # row and going backward. This makes handling line wraps simpler,
        # as we consume from the end of the last line and so forth.
        y = (min(self.rows,self.rows_needed())-1) * 8
        lines = self.lines[:]
        while y >= 0:
            if len(lines[-1]) == 0:
                lines.pop(-1)
                if len(lines) == 0: return # Should not happen
            to_consume = len(lines[-1]) % self.cols
            if to_consume == 0: to_consume = self.cols
            rowchars = lines[-1][-to_consume:] # Part to display from the end
            lines[-1]=lines[-1][:-to_consume]  # Remaining part.
            self.display.text(rowchars, 0, y, 1)
            y -= 8
        self.display.show()

    # Add a new line, without refreshing the display.
    def print(self,msg):
        self.lines.append(msg)
        self.lines = self.lines[-self.rows:]

