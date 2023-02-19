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
    unsigned char escape[8] = {1,1,0,0,0,0,1,1};

    unsigned char header[5] = {'F','C','0',width&0xff,height&0xff};
    fwrite(header,5,1,stdout);

    while(idx < bits) {
        int left = bits-idx; // Left bits

        /* Check next run len. */
        int first = image[idx];
        int j; // Total run len
        for (j = 1; j < C2_RUNLEN_MAX && j < left; j++)
            if (image[idx+j] != first) break;

        /* Let's try long form run length encoding. */
        if (j >= C2_RUNLEN_MIN) {
            idx += j;
            unsigned char seq[2] = {0xc3, first<<7 | ((j-16) & 0x7f)};
            fwrite(seq,2,1,stdout);
            continue;
        }

        /* Use escaping of special byte. */
        if (left >= 8 && !memcmp(image+idx,escape,8)) {
            idx += 8;
            unsigned char seq[2] = {0xc3, 0};
            fwrite(seq,2,1,stdout);
            continue;
        }
        
        /* Use verbatim. */
        unsigned char bits =
            (image[idx+0] << 7) |
            (image[idx+1] << 6) |
            (image[idx+2] << 5) |
            (image[idx+3] << 4) |
            (image[idx+4] << 3) |
            (image[idx+5] << 2) |
            (image[idx+6] << 1) |
            (image[idx+7] << 0);
        fwrite(&bits,1,1,stdout);
        idx += 8;
    }
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

    if (argc != 2) {
        fprintf(stderr,"Usage: %s <image.png>\n",argv[0]);
        exit(1);
    }

    /* Load the PNG in memory. */
    fp = fopen(argv[1],"rb");
    if (!fp) {
        perror("Opening PNG file");
        exit(1);
    }

    int width, height;

    if ((image = load_png(fp,&width,&height)) == NULL) {
        fprintf(stderr,"Invalid PNG image.\n");
        exit(1);
    }

    compress(image,width,height);

    fclose(fp);
    return 0;
}
