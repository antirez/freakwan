/* Copyright (c) 2023, Salvatore Sanfilippo <antirez at gmail dot com>
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 *   * Redistributions of source code must retain the above copyright notice,
 *     this list of conditions and the following disclaimer.
 *   * Redistributions in binary form must reproduce the above copyright
 *     notice, this list of conditions and the following disclaimer in the
 *     documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#define PNG_DEBUG 3
#include <png.h>

int debug_msg = 0;

/* Get the PNG data and return a 128x64 bytes array representing the
 * bitmap. The function converts the image into 1 bit of color,
 * using >= 128 as threshold. If the image is RGB, the average value
 * is taken. If the image is not a 128x64 image with color type
 * RGB, RGB_ALPHA or GRAY_ALPHA, NULL is returned.
 *
 * The image width and height, on success, are stored respectively
 * in 'wptr' and 'hptr'. */
#define PNG_BYTES_TO_CHECK 8
unsigned char *load_png(FILE *fp, int *wptr, int *hptr) {
    unsigned char buf[PNG_BYTES_TO_CHECK];
    png_structp png_ptr;
    png_infop info_ptr;
    png_uint_32 width, height, j;
    int color_type;

    /* Check signature */
    if (fread(buf, 1, PNG_BYTES_TO_CHECK, fp) != PNG_BYTES_TO_CHECK)
        return NULL;
    if (png_sig_cmp(buf, (png_size_t)0, PNG_BYTES_TO_CHECK))
        return NULL; /* Not a PNG image */

    /* Initialize data structures */
    png_ptr = png_create_read_struct(PNG_LIBPNG_VER_STRING,
        NULL,NULL,NULL);
    if (png_ptr == NULL) {
        return NULL; /* Out of memory */
    }

    info_ptr = png_create_info_struct(png_ptr);
    if (info_ptr == NULL) {
        png_destroy_read_struct(&png_ptr, NULL, NULL);
        return NULL;
    }

    /* Error handling code */
    if (setjmp(png_jmpbuf(png_ptr)))
    {
        png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
        return NULL;
    }

    /* Set the I/O method */
    png_init_io(png_ptr, fp);

    /* Undo the fact that we read some data to detect the PNG file */
    png_set_sig_bytes(png_ptr, PNG_BYTES_TO_CHECK);

    /* Read the PNG in memory at once */
    png_read_png(png_ptr, info_ptr, PNG_TRANSFORM_EXPAND, NULL);
    width = png_get_image_width(png_ptr, info_ptr);
    height = png_get_image_height(png_ptr, info_ptr);
    color_type = png_get_color_type(png_ptr, info_ptr);

    char *color_str = "unknown";
    switch(color_type) {
    case PNG_COLOR_TYPE_RGB: color_str = "RGB"; break;
    case PNG_COLOR_TYPE_RGB_ALPHA: color_str = "RGBA"; break;
    case PNG_COLOR_TYPE_GRAY: color_str = "GRAY"; break;
    case PNG_COLOR_TYPE_GRAY_ALPHA: color_str = "GRAYA"; break;
    case PNG_COLOR_TYPE_PALETTE: color_str = "PALETTE"; break;
    }

    fprintf(stderr,"%dx%d image, color:%s\n",(int)width,(int)height,color_str);
    if ((color_type != PNG_COLOR_TYPE_RGB &&
         color_type != PNG_COLOR_TYPE_RGB_ALPHA &&
         color_type != PNG_COLOR_TYPE_GRAY &&
         color_type != PNG_COLOR_TYPE_GRAY_ALPHA) ||
        (width > 256 || height > 256))
    {
        png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
        return NULL;
    }

    /* Get the image data */
    unsigned char **imageData = png_get_rows(png_ptr, info_ptr);
    unsigned char *bitmap = malloc(width*height);
    if (!bitmap) {
        png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
        return NULL;
    }

    for (j = 0; j < height; j++) {
        unsigned char *dst = bitmap+j*width;
        unsigned char *src = imageData[j];
        unsigned int i, r, g, b;

        for (i = 0; i < width; i++) {
            if (color_type == PNG_COLOR_TYPE_RGB_ALPHA ||
                color_type == PNG_COLOR_TYPE_RGB)
            {
                r = src[0];
                g = src[1];
                b = src[2];
                src += (color_type == PNG_COLOR_TYPE_RGB_ALPHA) ? 4 : 3;
            } else if (color_type == PNG_COLOR_TYPE_GRAY_ALPHA ||
                       color_type == PNG_COLOR_TYPE_GRAY)
            {
                r = b = g = src[0];
                src += (color_type == PNG_COLOR_TYPE_GRAY_ALPHA) ? 2 : 1;
            }
            *dst++ = ((r+g+b)/3) >= 128;
        }
    }

    /* Free the image and resources and return */
    png_destroy_read_struct(&png_ptr, &info_ptr, NULL);
    if (hptr) *hptr = height;
    if (wptr) *wptr = width;
    return bitmap;
}

#define C2_RUNLEN_MIN 17
#define C2_RUNLEN_MAX (127+16)
void compress(unsigned char *image, int width, int height) {
    int bits = width*height; // Total bits in the image.
    int idx = 0; // Current index, next pixels to compress.
    unsigned char escape1[8] = {1,1,0,0,0,0,1,1}; /* Long run length. */
    unsigned char escape2[8] = {0,0,1,1,1,1,0,1}; /* Short W+B run. */
    unsigned char escape3[8] = {0,1,1,0,0,1,0,1}; /* SHort B+W run. */

    // Some compression stats to output.
    int stats_verb = 0;     // Verbatim bytes emitted.
    int stats_short = 0;    // Short runs emitted.
    int stats_long = 0;     // Long runs emitted.
    int stats_escape = 0;   // Verbatim needing zero byte.
    int stats_bytes = 0;    // Total bytes

    unsigned char header[5] = {'F','C','0',width&0xff,height&0xff};
    fwrite(header,5,1,stdout);
    stats_bytes += 5;

    while(idx < bits) {
        int left = bits-idx; // Left bits

        /* Check next run len. */
        int first = image[idx];
        int j; // Total run len
        for (j = 1; j < C2_RUNLEN_MAX && j < left; j++)
            if (image[idx+j] != first) break;

        /* Let's try long form run length encoding. */
        if (j >= C2_RUNLEN_MIN) {
            unsigned char seq[2] = {0xc3, first<<7 | ((j-16) & 0x7f)};
            if (debug_msg)
                fprintf(stderr,"long run %02x%02x %d at %d\n",
                    seq[0],seq[1],j,idx);
            fwrite(seq,2,1,stdout);
            idx += j;
            stats_long++;
            stats_bytes += 2;
            continue;
        }

        /* Let's try short form run length encoding, that is useful
         * to encode, in a single byte, a run of black+white pixels
         * (or the other way around) so that the sum of the runs
         * is > 16, and each run is at max 16. */
        if (j > 1) {
            int j2; // Check next run
            for (j2 = 1; j2 < 16 && j2 < left-j; j2++)
                if (image[idx+j+j2] == first) break;

            /* It is useful to use a short run encoding only if
             * we actually save space. */
            if (j+j2 > 16) {
                unsigned char seq[2] = {
                    first ? 0x3d : 0x65,
                    ((j-1) << 4) | (j2-1)
                };
                if (debug_msg)
                    fprintf(stderr,"short run %02x%02x %d,%d at %d\n",
                        seq[0],seq[1],j,j2,idx);
                fwrite(seq,2,1,stdout);
                idx += j+j2;
                stats_short++;
                stats_bytes += 2;
                continue;
            }
        }

        /* Use escaping of special byte. */
        if (left >= 8 &&
            (!memcmp(image+idx,escape1,8) ||
             !memcmp(image+idx,escape2,8) ||
             !memcmp(image+idx,escape3,8)))
        {
            idx += 8;
            unsigned char seq[2] = {0xc3, 0};
            fwrite(seq,2,1,stdout);
            stats_escape++;
            stats_bytes += 2;
            continue;
        }
        
        /* Use verbatim. */
        if (debug_msg) fprintf(stderr,"verb at %d\n",idx);
        unsigned char verb = 0;
        for (int b = 7; b >= 0 && idx < bits; b--)
            verb |= image[idx++] << b;
        fwrite(&verb,1,1,stdout);
        stats_verb++;
        stats_bytes++;
    }
    fprintf(stderr,"Compressed to %d byte (%.2f%% orig size)\n", stats_bytes,
                    (float)stats_bytes/(width*height/8)*100);
    fprintf(stderr,"%d verbatim, %d short, %d long, %d escape\n",
                    stats_verb, stats_short, stats_long, stats_escape);
}

/* Load and uncompress an FCI image. On error abort the program.
 * On success an array of bytes, with white pixels set to 1, is returned.
 * The width and height info are filled by reference in wptr,hptr. */
unsigned char *load_fci(FILE *fp, int *wptr, int *hptr) {
    unsigned char hdr[5];
    if (fread(hdr,1,5,fp) != 5 || memcmp(hdr,"FC0",3)) {
        fprintf(stderr, "Error loading FCI header.\n");
        exit(1);
    }
    int width = hdr[3];
    int height = hdr[4];
    printf("FCI file, %dx%d\n", width, height);

    int bits = width*height;
    *wptr = width;
    *hptr = height;
    unsigned char *image = malloc(bits);
    if (image == NULL) {
        fprintf(stderr, "Out of memory loading FCI image.\n");
        exit(1);
    }

    int idx = 0; // Index inside the image data.
    while(!feof(fp) && idx < bits) {
        unsigned char data[2];
        fread(data,1,1,fp);

        /* Long run? */
        if (data[0] == 0xc3) {
            fread(data+1,1,1,fp);
            if (data[1] != 0) {
                /* Run len decode. */
                int runlen = (data[1]&0x7F)+16;
                int bit = data[1]>>7;
                while(runlen-- && idx < bits)
                    image[idx++] = bit;
                continue;
            } else {
                // Go to Verbatim code path.
            }
        }

        /* Short run? */
        if (data[0] == 0x3d || data[0] == 0x65) {
            fread(data+1,1,1,fp);
            if (data[1] != 0) {
                /* W+B or B+W decode. */
                int runlen1 = ((data[1] & 0xf0)>>4)+1;
                int runlen2 = (data[1] & 0x0f)+1;
                int bit = data[0] == 0x3d;
                while(runlen1-- && idx < bits)
                    image[idx++] = bit;
                while(runlen2-- && idx < bits)
                    image[idx++] = !bit;
                continue;
            } else {
                // Go to Verbatim code path.
            }
        }

        /* Verbatim. */
        for (int bit = 7; bit >= 0; bit--) {
            if (idx < bits)
                image[idx++] = (data[0] >> bit) & 1;
        }
    }
    return image;
}

/* Show the image on the terminal. */
void show_image_ascii(unsigned char *image, int width, int height) {
    /* Show image on the terminal, for now... */
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            printf("%c", image[y*width+x] ? '#' : ' ');
        }
        printf("\n");
    }
}

int main(int argc, char **argv)
{
    FILE *fp;
    unsigned char *image;
    int width, height;

    if (argc != 3) {
        fprintf(stderr,"Usage: %s compress image.png > image.fci\n",argv[0]);
        fprintf(stderr,"       %s show image.fci\n",argv[0]);
        exit(1);
    }

    /* Open FCI or PNG file. */
    fp = fopen(argv[2],"rb");
    if (!fp) {
        perror("Opening input file");
        exit(1);
    }

    if (!strcasecmp(argv[1],"compress")) {
        if ((image = load_png(fp,&width,&height)) == NULL) {
            fprintf(stderr,"Invalid PNG image.\n");
            exit(1);
        }
        compress(image,width,height);
    } else if (!strcasecmp(argv[1],"show")) {
        image = load_fci(fp,&width,&height);
        show_image_ascii(image,width,height);
    } else {
        fprintf(stderr,"Wrong command: %s", argv[1]);
        exit(1);
    }

    fclose(fp);
    return 0;
}
