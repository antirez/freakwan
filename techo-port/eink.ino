/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#include <GxEPD.h>
#include <GxDEPG0150BN/GxDEPG0150BN.h>  // 1.54" b/w LILYGO T-ECHO display
#include <Fonts/FreeMono9pt7b.h>
#include <GxIO/GxIO_SPI/GxIO_SPI.h>
#include <GxIO/GxIO.h>
#include <ctype.h>

GxEPD_Class *display   = nullptr;       // E-ink display object.

void setupDisplay() {
    SPIClass *dispPort = new SPIClass(
        /*SPIPORT*/NRF_SPIM2,
        /*MISO*/ ePaper_Miso,
        /*SCLK*/ePaper_Sclk,
        /*MOSI*/ePaper_Mosi);

    GxIO_Class *io = new GxIO_Class(
        *dispPort,
        /*CS*/ ePaper_Cs,
        /*DC*/ ePaper_Dc,
        /*RST*/ePaper_Rst);

    display = new GxEPD_Class(
        *io,
        /*RST*/ ePaper_Rst,
        /*BUSY*/ ePaper_Busy);

    dispPort->begin();
    display->init(/*115200*/);
    display->fillScreen(GxEPD_WHITE);
    display->setTextColor(GxEPD_BLACK);
}

void setDisplayBacklight(bool en) {
    digitalWrite(ePaper_Backlight, en);
}

/* State of our terminal-alike display abstraction. */
struct {
    int xres = 200;
    int yres = 200;
    int font_height = 13;   // Font height (including spacing).
    int font_width = 10;    // Font width (including spacing).
    int y = 0;  // Y coordinate of last line written.
    int first_update_needed = true; // Full update never did so far.
} Scroller;

/* Show some text in the device display, wrapping as needed and refreshing
 * the screen if there is not enough room. */
void displayPrint(const char *str) {
    display->setFont(&FreeMono9pt7b);
    display->setRotation(3);

    int len = strlen(str);
    int cols = Scroller.xres / Scroller.font_width;
    int rows = Scroller.yres / Scroller.font_height;
    int rows_needed = (len+cols-1)/cols;
    int rows_avail = (Scroller.yres-Scroller.y)/Scroller.font_height;
    int full_update = false; // True if we need a full screen update cycle.

    /* Screen is full? Clean it and start from top. */
    if (rows_avail < rows_needed) {
        Scroller.y = 0;
        display->fillScreen(GxEPD_WHITE);
        full_update = true;
    }

    /* String too long for the screen? Trim it. */
    if (rows_needed > rows) {
        int maxchars = rows*cols;
        str += len-maxchars;
    }

    int x = 0;
    Scroller.y += Scroller.font_height;
    while(*str) {
        if (isprint(str[0]))
            display->drawChar(x, Scroller.y, str[0], GxEPD_BLACK, GxEPD_WHITE, 1);
        str++;
        x += 10;
        if (x+10 >= Scroller.xres) {
            x = 0;
            Scroller.y += Scroller.font_height;
        }
    }

    if (full_update || Scroller.first_update_needed) {
        display->update();
        Scroller.first_update_needed = false;
    } else {
        int start_y = Scroller.y - Scroller.font_height * rows_needed;
        int stop_y = Scroller.y;
        if (start_y < 0) start_y = 0;
        if (stop_y >= Scroller.yres) stop_y = Scroller.yres-1;
        display->updateWindow(0,start_y,Scroller.xres-1,stop_y,true);
    }
}

/* Show the specified 1-bit per pixel bitmap on the screen. If not enough
 * vertical space is left, the screen is refreshed. */
void displayImage(const uint8_t *bitmap, int width, int height) {
    display->setRotation(3);
    int height_available = Scroller.yres - Scroller.y;
    bool full_update = 0;

    /* Check if we have enough room. */
    if (height_available < height) {
        Scroller.y = 0;
        display->fillScreen(GxEPD_WHITE);
        full_update = true;
    }

    /* Render pixels on the screen. */
    for (int h = 0; h < height; h++) {
        for (int w = 0; w < width; w++) {
            if (bitmap[h*width+w] && w < Scroller.xres && h < Scroller.yres)
                display->drawPixel(w,Scroller.y+h,GxEPD_BLACK);
        }
    }

    /* Update and adjust y offset. */
    if (full_update || Scroller.first_update_needed) {
        display->update();
        Scroller.first_update_needed = false;
    } else {
        int stop_y = Scroller.y + height;
        if (stop_y >= Scroller.yres) stop_y = Scroller.yres-1;
        display->updateWindow(0,Scroller.y,Scroller.xres-1,stop_y,true);
    }
    Scroller.y += height;
}
