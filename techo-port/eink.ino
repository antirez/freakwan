#include <GxEPD.h>
#include <GxDEPG0150BN/GxDEPG0150BN.h>  // 1.54" b/w LILYGO T-ECHO display
#include <Fonts/FreeMono9pt7b.h>
#include <GxIO/GxIO_SPI/GxIO_SPI.h>
#include <GxIO/GxIO.h>

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
} Scroller;

void displayPrint(const char *str) {
    display->setFont(&FreeMono9pt7b);
    display->setRotation(3);

    int len = strlen(str);
    int cols = Scroller.xres / Scroller.font_width;
    int rows = Scroller.yres / Scroller.font_height;
    int rows_needed = (len+cols-1)/cols;
    int rows_avail = (Scroller.yres-Scroller.y)/Scroller.font_height;

    SerialMon.print("Needed: "); SerialMon.println(rows_needed);
    SerialMon.print("Avail : "); SerialMon.println(rows_avail);

    /* Screen is full? Clean it and start from top. */
    if (rows_avail < rows_needed) {
        Scroller.y = 0;
        display->fillScreen(GxEPD_WHITE);
    }

    /* String too long for the screen? Trim it. */
    if (rows_needed > rows) {
        int maxchars = rows*cols;
        str += len-maxchars;
    }

    int x = 0;
    Scroller.y += Scroller.font_height;
    while(*str) {
        display->drawChar(x, Scroller.y, str[0], GxEPD_BLACK, GxEPD_WHITE, 1);
        str++;
        x += 10;
        if (x+10 >= Scroller.xres) {
            x = 0;
            Scroller.y += Scroller.font_height;
        }
    }
    display->update();
}
