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

The image header is just two bytes W+H, unsigned chars from 0 to 255,
specifying the image width and height in pixels, so images up to
255x255 pixels are supported.

All groups of 8 pixels (scanning from top-left to bottom-right) are sent
verbatim as a single byte, with the exception of the following two sequences:

    01101001 (escape)

When the escape occurs, it means the pixels verbatim if the next byte is 0,
otherwise the next byte is as follows:

    blllllll

Where b is 1 o 0, depending on the fact this is a run of zeros or ones,
and lllllll is an unsigned integer. The value of lllllll is guaranteed to
be *at least 1* (so the next byte will never be zero if we don't want
to mean the escape bits verbatim). This value, we add 16, and that is the
length of the run of consecutive pixels. So this format is only used for
runs >= 17 (since up to 16 it is just better to emit the verbatim bytes) and
the maximum run it can represent is 16+127 = 143 pixels of the same color.

The last byte may encode more pixels than the ones needed in order to
finish the image. In such case the decoder should discard the extra bits.

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

    01101001 + 0|0000010 (run of 0 bits, 16+2 = 18) (2 bytes so far)

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
.*.**.*.
.*****..
...**...
```

At some point we would have...

    10010001 (3 bytes)
    11111011 (4 bytes)
    11111101 (5 bytes)
    01101001 (6 bytes: but it is the escape sequence!)

So to tell the decoder that we meant exactly that sequence of
pixels, we emit a zero byte:

    00000000 (7 bytes)
    ... other bytes follow normally...

And that's it \o/
