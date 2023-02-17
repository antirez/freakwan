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
    /* Characters after 127, starting from 128, are used to represent
     * certain selected unicode characters, like è, é, and a few more,
     * for a total of 64 symbols. */
    unsigned char font[(127+64)*3] = {0}; /* Each characters takes 3 bytes. */
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

        if (l == 1 || (l > 5 && !memcmp(buf,"byte:",5))) {
            /* Single letter or byte:<int>: we are at the start of a new
             * font character. */
            if (l == 1)
                cur_char = buf[0];
            else
                cur_char = atoi(buf+5);
            if (cur_char < 0 || cur_char > (int)sizeof(font)/3) {
                fprintf(stderr,"Out of bound char: %c in line %d\n",
                    cur_char, line);
                exit(1);
            }
            if (cur_scanline != 0 && cur_scanline != 6) {
                fprintf(stderr,"Found new character but previous was not closed in line %d\n", line);
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

    /* Now, for all the missing characters, use a checkboard pattern
     * so that it is clear that something is missing. */
    for (int j = 0; j < (int)sizeof(font)/3; j++) {
        if (j == ' ') continue; // That's empty for a reason.
        if (font[j*3] == 0 && font[j*3+1] == 0 && font[j*3+2] == 0) {
            font [j*3] = 0x5a;
            font [j*3+1] = 0x5a;
            font [j*3+2] = 0x5a;
        }
    }

    printf("FontData4x6 = b'");
    for (int j = 0; j < (int)sizeof(font); j++)
        printf("\\x%02x",font[j]);
    printf("'\n");
}
