**Note: this is still a work in progress, only the font description is there, all the rest of the code is to be written.**

# 4x6 font for FreakWAN

I started from the font originally found [here](https://github.com/filmote/Font4x6/blob/master/src/fonts/Font4x6.cpp). Thanks to Simon Holmes for releasing it into the BSD license. Then I added the symbols, that were almost completely missing. The representation of the font is now different, designed for easy adding of new characters and Python conversion. The scanline is now horizontal, and not vertical, and each byte reprents two scalines (4 bits each), so every letter is just three bytes in memory. Certian characters were shifted so that all characters will fit in a 6x4 grid, in order to be able to print them with just one pixel of vertical space if desired.

# How to modify the font

You manipulate the font in `font_descr.txt`, then convert it to Python
using the C program `font_conv.c`. The result is a Python bytes type
with `191*3` bytes (191 mappable characters max: ASCII set up to 127,
the a few special chars we define to map specific UTF-8 chars and status
icons), in order to speedup indexing during font rendering. The code to
render the font is inside the FreakWAN project itself, and is quite simple:
just draws pixels according to the scanlines bit configuration.
