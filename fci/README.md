# FreakWAN Compressed Image (.fci file format)

This is the FreakWAN image format, designed for small 1 bit
color images. The point is compressing obvious patterns in
black and white images, while resisting hard to compress images
(especially dithered, as dithering is very random alike and difficult
to compress), to avoid ending with a compressed images larger than the
original ones. The header information is minimal for the same reason.

Before arriving at this extremely simple algorithm I tried other two
much complex ones, one of which dealt with images in 8x8 blocks
encoding differences compared to known blocks. In the end, while
more complex algorithms worked better with certain images, the trivial
algorithm that follows was comparable, since it uses very little
extra space in case of hard to compress images. The more complex
algorithms did better in images where there were more patterns
to exploit.

# Specification

The image header is just three verbatim bytes "FC0" followed by two
8 bit unsigned bytes "WH", from 0 to 255, specifying the image width and
height in pixels, so images up to 255x255 pixels are supported.
The first try bytes, "FC", is the "magic value" to understand if it
is actually an FC file. The third byte is the format used. The
format "0" is what is described in this document.

All groups of 8 pixels (scanning from top-left to bottom-right) are sent
verbatim as a single byte, with the exception of the following sequence
of pixels, called the escapes:

    0xC3 11000011 (long run escape)
    0x3D 00111101 (short run white+black escape)
    0x65 01100101 (short run black_white escape)

When the long run escape occurs (0xc3), it means the pixels verbatim if the
next byte is 0, otherwise the next byte is as follows:

    blllllll

Where b is 1 o 0, depending on the fact this is a run of zeros or ones,
and lllllll is an unsigned integer. The value of lllllll is guaranteed to
be *at least 1* (so the next byte will never be zero if we don't want
to mean the escape bits verbatim). This value, we add 16, and that is the
length of the run of consecutive pixels. So this format is only used for
runs >= 17 (since up to 16 it is just better to emit the verbatim bytes) and
the maximum run it can represent is 16+127 = 143 pixels of the same color.

When short run escape byte is read (0x3d or 0x65), then if the following
byte is 0 the decoder should just ouput the verbatim bits (3D or 65 in
binary), otherwise the next byte is as follows:

    wwwwbbbb (0x3d escape)
    bbbbwwww (0x65 escape)

In this case wwww and bbbb should be read as 4 bits unsigned integers
plus 1, (so they can range from 1 to 16), and the decoder should output
'w+1' white pixels followed by 'b+1' black pixels, or the other way around
for the other escape. Note that this escape is emitted only when the
sum of white and black pixels is > 16 (otherwise we would waste space
compared to verbatim bytes), so the lengths byte will never be zero.

At the end of the image, the last verbatim byte may encode more pixels than
the ones needed in order to finish the image. In such case the decoder
should discard the extra bits.

## Example

Let's compress the following 8x8 image (`.` = 0, `#` = 1):

```
........
........
..*..*..
.******.
********
.******.
..****..
...**...
```

There is a first run of 18 zeros, so we emit the escape sequence byte
followed by a run length byte:

    11000011 + 0|0000010 (run of 0 bits, 16+2 = 18) (2 bytes so far)

After that there are runs that are always smaller than 17, so we
emit verbatim bits:

    10010001 (3 bytes)
    11111011 (4 bytes)
    11111101 (5 bytes)
    11111000 (6 bytes)
    11110000 (7 bytes)
    011000[00] (8 bytes)

Last two bits are padding, discarded by the decoder.
While we were able to save 2 bits, compared of the length
of the original image, padding wasted it, so we encoded
64 bits into 64 bits. But larger images with long runs
do better.

However we were lucky as our escape sequence never appears
in normal runs of pixels. If the image was a bit different,
like that:

```
........
........
..*..*..
.******.
********
.***....
******..
...**...
```

At some point we would have...

    10010001 (3 bytes)
    11111011 (4 bytes)
    11111101 (5 bytes)
    11000011 (6 bytes: but it is the escape sequence!)

So to tell the decoder that we meant exactly that sequence of
pixels, we emit a zero byte:

    00000000 (7 bytes)
    ... other bytes follow normally...

And that's it \o/

# Appendix: other algorithms explored

The following algorithms are the others I evaluated. They produce better
results on more regular images, but the additional complexity for
relatively little gains made no sense in an embedded context. However
I will left them here for further future analysis.

# Discarded algorithm 1: More complex run length encoding

This is the FreakWAN image format, designed for 128x64 pixels 1 bit
of color images. The point is compressing obvious patterns in dithered
black and white images, triyng to avoid any useless information such
as the header, if not for the two byes of image size (but right now
all the images are 128x64 bytes).

The header is just "FC1" followed by the two bytes WH, 8 bit unsigned integers
with the width and height of the image.

Then a sequence of the following bytes follow, up to representing
the whole WxH bits of the image. If the last byte represents more
bits than WxH would fit, the final bits are just discarded by the
decoder.

```
00vvvvvv = 6 verbatim "vvvvvv" pixels of the image, as they appear
01bwbwbw = b = 0, one 0 pixel, b = 1 two 0 pixels, ... and so forth
           for w (white) pixels. so 01110010 means:
            2 black, 2 white, 1 black, 1 white, two black 1 white
10wbwbwb = Like the above but sequence starts with white pixels.
110lllll = lllll: 1 based len run of pixels of value 0
111lllll = lllll: 1 based len run of pixels of value 1
```

Note: in the above description black menas a bit value of 0, white
a bit value of 1.

# Discarded algorithm 2: Block difference encoding.

In this scheme the image is divided in 8x8 areas, from the top-left,
to the bottom-right. Each area is encoded independently in the
following way:

Each block starts with a byte where the bits have the following meaning:

ipppllll

ppp is three bits representing a number from 0 to 7, selecting
an initial block pattern among the following, where . means
bit set to 0 and # means bit set to 1. There are 6 possible
blocks from 0 to 5, since pattern ID 6 and 7 have a special meaning
that we will cover later:

```
Patter 0:
........
........
........
........
........
........
........
........
```

```
Patter 1:
........
........
........
........
########
########
########
########
```

```
Patter 2:
#.......
##......
###.....
####....
#####...
######..
#######.
########
```

```
Patter 3:
.......#
......##
.....###
....####
...#####
..######
.#######
########
```

```
Patter 4:
....####
....####
....####
....####
....####
....####
....####
....####
```

```
Patter 5:
#.#.#.#.
.#.#.#.#
#.#.#.#.
.#.#.#.#
#.#.#.#.
.#.#.#.#
#.#.#.#.
.#.#.#.#
```

The bit 'i' means inverted. If it is set to i, the initial block
pattern selected by the block type is inverted: bits 0 will be
turend to 1 and bits 1 to 0.

After the initial block configuration is loaded, it is followed
by a sequence of coordinates inside the block to invert, in order to
reach the block configuration of the original image. The number of
"pixel changes" following is provided by the four bits "llll", that
is an integer between 0 and 15.

For example the byte `0|000|0100` means:
* Pattern not inverted
* Pattern ID: 0
* Number of changes to make: 4

## Change bytes

After a block type from 0 to 5, the specified number (N) of pixel changes will
follow. They are just a bitmap of N pairs of 3 bit unsigned integer numbers,
rounded to mulitple of 8 bits. For instance if three pixels change follow
then three pixels will be sent after the block type byte:

```
xxxyyyxx|xyyyxxxy|yypppppp
```

The last 6 bits, "pppppp" are just padding. Each x,y coordinate, where each
value is 0-7,0-7 represents a bit to invert in the original pattern selected
by the first byte.

## Verbatim block

The special pattern ID value 6 means that a "verbatim" 8x8 block is
following, in case the 8x8 pattern can't be encoded efficiently as
difference of one of the above patterns. So after a pattern ID 7
8 bytes with the 64 bits will follow, from the top to the bottom scan
line:

```
........  First byte
........  Second byte
........  Third byte
........  ... and so forth
........
........
........
........
```

## Copy block

The special pattern ID 7 means "copy". It is used when the 8x8
pattern was already seen in the image. The next byte will be a
number between 0 to 255 indicating which 8x8 block it is, as
an offset relative to the current block, where: 0 means to
copy the block immedialely before, 1 to copy two blocks before
and so forth. If 'i' is set, the block to copy must be
inverted. When ID is 7, the "llll" bits have a new special
meaning:

```
i111xxyy + oooooooo
```

Where `i` is the inverted bit, `111` is ID 7, `xx` and `yy` are
shift factors to apply to x and y, betwen 0 to 3, to the block to
copy. `oooooooo` is the offset of the block, as specified above.
Shifting means to move all the pixels on the right (xx)
or on the bottom (yy), with pixels wrapping around to return
back from left/top. For instance the following block:

```
........
........
.....##.
....####
.....###
........
.......#
........
```

With xx shift = 1, yy shift = 2, will become:

```
#.......
........
........
........
......##
#....###
#.....##
........
```

## Block type choice

A verbatim block (special type 6) will require 9 bytes to represent
an 8x8 blocks (wasting 1 byte compared to an uncompressed representation).
So the compression algorithm should try selecting a different encoding
only when it requires less then 9 bytes.

For block patterns from 0 to 5, considering the initial byte and the
following changes bytes, the maximum number of changes to use less than
9 bytes is the following:

```
Byte 0 (type 1, inverted, 9 changes): 1001-0101
Byte 1-3: xxxyyyxx|xyyyxxxy|yyxxxyyy|
Byte 4-6: xxxyyyxx|xyyyxxxy|yyxxxyyy|
Byte 7: xxxyyypp
```

So this encoding should be used when the pattern and the block to encode
have a maximum difference of 9 pixels. To check this is quite simple:
for each block of the image, we just need to xor all our patterns and
their inversions with the image block, and count the pixels that are
still set after the xor. Then use the block with the smallest difference,
assuming we found one with 9 or less different pixels.

The special block type 7, that is the copy block, uses just two bytes
to represent 8 bytes of data. However this is still more than the minimum
space required by blocks without changes at all compared to one of the
patterns, that use a single byte. So the following algorithm should be
used, when compressing each block of the image:

Foreach block in the image, from left to right (rounding the image width
and height to the first multiples of 8, setting non existing bits to 0):

1. Test all the block patterns to see if we find a candidate requiring
no pixel changes at all (single byte). If found, output it and go
to the next block of the image. Otherwise we just remember the block
type that required the minimum number of changes, and what this number
of changes is.
2. Test all the 256 previous blocks to see if there is one we can
use to encode with a copy block. For each block we perform the xor to see if
the whole block becomes 0, and we also test all the shifts offsets
and for eacho one we try to invert it. If we find a candidate, we use it.
3. If at step 1 we found a block with pattern requiring 9 or less changes, use it and go to the next block.
4. Use a verbatim block.

## Header

The image data is prefixed by "FC2" plus two bytes header, that is just the two bytes WH, 8 bit unsigned integers each, with the width and height of the image. We don't support images larger than 256x256 in FreakWAN, being the display
just 128x64 pixels.
