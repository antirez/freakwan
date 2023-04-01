#include <string.h> // memcpy()
#include <stdint.h>

/* Uncompress an FCI image. On format error, NULL is returned.
 * On success, a heap allocated array of bytes, with white pixels set to 1, is
 * returned. The width and height info are filled by reference in wptr,hptr. */
uint8_t *decode_fci(uint8_t *data, size_t datalen, int *wptr, int *hptr) {
    size_t left = datalen; // Bytes yet to consume from data.

    /* Load the image header. */
    if (left < 5) return NULL;
    if (memcmp(data,"FC0",3)) {
        return NULL; // Magic mismatch.
    }
    int width = data[3];
    int height = data[4];
    data += 5; left -= 5;

    /* Allocate the bitmap. */
    int bits = width*height;
    *wptr = width;
    *hptr = height;
    uint8_t *image = (uint8_t*) malloc(bits);
    if (image == NULL) {
        return NULL;
    }

    int idx = 0; // Index inside the image data.
    while(left > 0 && idx < bits) {
        unsigned char op[2];
        op[0] = data[0];
        op[1] = left > 1 ? data[1] : 0;

        if (op[0] == 0xc3) {
            /* Long run? */
            data += 2; left -= 2;
            if (op[1] != 0) {
                /* Run len decode. */
                int runlen = (op[1]&0x7F)+16;
                int bit = op[1]>>7;
                while(runlen-- && idx < bits)
                    image[idx++] = bit;
                continue;
            } else {
                // Continue to Verbatim code path.
            }
        } else if (op[0] == 0x3d || op[0] == 0x65) {
            /* Short run? */
            data += 2; left -= 2;
            if (op[1] != 0) {
                /* W+B or B+W decode. */
                int runlen1 = ((op[1] & 0xf0)>>4)+1;
                int runlen2 = (op[1] & 0x0f)+1;
                int bit = op[0] == 0x3d;
                while(runlen1-- && idx < bits)
                    image[idx++] = bit;
                while(runlen2-- && idx < bits)
                    image[idx++] = !bit;
                continue;
            } else {
                // Continue to Verbatim code path.
            }
        } else {
            data += 1; left -= 1;
        }

        /* Verbatim. */
        for (int bit = 7; bit >= 0; bit--) {
            if (idx < bits)
                image[idx++] = (op[0] >> bit) & 1;
        }
    }
    return image;
}
