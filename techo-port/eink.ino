#include <GxEPD.h>
#include <GxDEPG0150BN/GxDEPG0150BN.h>  // 1.54" b/w LILYGO T-ECHO display
#include <Fonts/FreeMonoBold12pt7b.h>
#include <Fonts/FreeSans9pt7b.h>
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
    int y = 12;      // Y coordinate of next line to write.
} Scroller;

void displayPrint(const char *str) {
    display->setFont(&FreeMonoBold12pt7b);
    display->setRotation(3);
    int x = 0;
    const char *p = str;
    while(*p) {
        display->drawChar(x, Scroller.y, p[0], GxEPD_BLACK, GxEPD_WHITE, 1);
        p++;
        x += 12;
    }
    Scroller.y += 12;
    display->update();
}
