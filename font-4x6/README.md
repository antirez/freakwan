**Note: this is still a work in progress, only the font description is there, all the rest of the code is to be written.**

# 4x6 font for FreakWAN

Font originally from [here](https://github.com/filmote/Font4x6/blob/master/src/fonts/Font4x6.cpp), thanks to Simon Holmes for releasing it into the BSD license.The representation is now different, designed for easy adding of new characters and Python conversion. The scanline is now horizontal and not vertical, and each byte reprents two scalines (4 bits each), so every letter is just two bytes in memory. Certian characters were shifted so that all characters will fit in a
6x4 grid. In order to be able to print them with just one pixel of vertical
space if desired.

# How to modify the font

You manipulate the font in `font_descr.txt`, then convert it to Python
using the C program `font_conv.c`. The result is a Python bytes type
with 256 bytes (128 mappable characters max), in order to speedup indexing
during font rendering. The code to render the font is inside the FreakWAN
project itself, and is quite simple: just draws pixels according to the
scanlines bit configuration.
