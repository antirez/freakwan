/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

int main(void) {
    FILE *fp = fopen("font_descr.txt","r");
    if (!fp) {
        perror("Opening font_descr.txt");
        exit(1);
    }

    char buf[1024];
    unsigned char font[128*3] = {0}; /* 128 font characters x 3 bytes each. */
    int cur_char = -1; /* -1 = No current character selected. */
    int cur_scanline = 0; /* Each character has 6 scanlines */
    int line = 0;   /* Current line number. */
    while(fgets(buf,sizeof(buf),fp) != NULL) {
        line++;
        size_t l = strlen(buf);
        if (buf[l-1] == '\n') {
            buf[l-1] = 0;
            l--;
        }
        if (l == 0) continue; /* Skip empty lines. */

        if (l == 1) {
            /* Len 1: we are at the start of a new font character. */
            cur_char = buf[0];
            if (cur_char < 0 || cur_char > 127) {
                fprintf(stderr,"Out of bound char: %c\n", cur_char);
                exit(1);
            }
            cur_scanline = 0;
        } else if (l == 4) {
            /* Len 4: this is one of the fonts scanline. */
            int bits = (buf[0] == '#') << 3 |
                       (buf[1] == '#') << 2 |
                       (buf[2] == '#') << 1 |
                       (buf[3] == '#') << 0;
            int byte = cur_char*3 + cur_scanline/2;
            if (!(cur_scanline & 1)) bits <<= 4;
            font[byte] = font[byte] |= bits;
            cur_scanline++;

            /* We expect to have a selected character. */
            if (cur_char == -1) {
                fprintf(stderr,"Syntax error in line %d", line);
                exit(1);
            }
        }
    }

    printf("FontData4x6 = b'");
    for (int j = 0; j < 128*3; j++)
        printf("\\x%02x",font[j]);
    printf("'\n");
}
