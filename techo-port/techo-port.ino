#include "hwconfig.h"
#include <SPI.h>
#include <Wire.h>

#include <GxEPD.h>
#include <GxDEPG0150BN/GxDEPG0150BN.h>  // 1.54" b/w LILYGO T-ECHO display

#include <Fonts/FreeMonoBold12pt7b.h>
#include <Fonts/FreeSans9pt7b.h>
#include <GxIO/GxIO_SPI/GxIO_SPI.h>
#include <GxIO/GxIO.h>

#include <RadioLib.h>

void setupDisplay();
void enableBacklight();
void configVDD(void);
void boardInit();
void LilyGo_logo(void);
void setupLoRa();

SPIClass        *dispPort  = nullptr;       // SPI to e-ink display
SPIClass        *rfPort    = nullptr;       // SPI to SX1262
GxIO_Class      *io        = nullptr;
GxEPD_Class     *display   = nullptr;       // e-ink display object
SX1262          radio     = nullptr;        // LoRa radio object

uint32_t        blinkMillis = 0;
uint8_t rgb = 0;

void setup()
{
    Serial.begin(115200);
    delay(200);
    boardInit();
    delay(200);
    LilyGo_logo();
}

void loop()
{
    static int total_loops = 0;
    
    if (millis() - blinkMillis > 300) {

        blinkMillis = millis();
        switch (rgb) {
        case 0:
            digitalWrite(GreenLed_Pin, LOW);
            digitalWrite(RedLed_Pin, HIGH);
            digitalWrite(BlueLed_Pin, HIGH);
            break;
        case 1:
            digitalWrite(GreenLed_Pin, HIGH);
            digitalWrite(RedLed_Pin, LOW);
            digitalWrite(BlueLed_Pin, HIGH);
            break;
        case 2:
            digitalWrite(GreenLed_Pin, HIGH);
            digitalWrite(RedLed_Pin, HIGH);
            digitalWrite(BlueLed_Pin, LOW);
            break;
        default :
            break;
        }
        rgb++;
        rgb %= 3;
        SerialMon.print("Looping: ");
        SerialMon.println(total_loops);

        if (total_loops++ == 1000) NRF_POWER->SYSTEMOFF = 1;
    }
}

void LilyGo_logo(void)
{
    display->setFont(&FreeMonoBold12pt7b);
    display->setRotation(3);
    display->fillScreen(GxEPD_WHITE);
    display->drawChar(100, 100, 'P', GxEPD_BLACK, GxEPD_WHITE, 2);
    display->update();
    
    display->fillRect(50, 50, 50, 50, GxEPD_BLACK);
    display->drawChar(20, 40, 'a', GxEPD_BLACK, GxEPD_WHITE, 1);
    display->setFont(&FreeSans9pt7b);
    display->drawChar(35, 40, 'b', GxEPD_BLACK, GxEPD_WHITE, 1);
    display->drawChar(50, 40, 'c', GxEPD_BLACK, GxEPD_WHITE, 1);
    
    // display->updateWindow(0,0,200,200,false);
    display->updateWindow(0,0,100,100,true);
    delay(2000);
    display->fillRect(20, 20, 50, 50, GxEPD_WHITE);
    display->updateWindow(0,0,100,100,true);
    delay(2000);
    display->update();
    setupLoRa();
}

void enableBacklight(bool en)
{
    digitalWrite(ePaper_Backlight, en);
}

void setupDisplay()
{
    dispPort = new SPIClass(
        /*SPIPORT*/NRF_SPIM2,
        /*MISO*/ ePaper_Miso,
        /*SCLK*/ePaper_Sclk,
        /*MOSI*/ePaper_Mosi);

    io = new GxIO_Class(
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
    display->setRotation(2);
    display->fillScreen(GxEPD_WHITE);
    display->setTextColor(GxEPD_BLACK);
}

void configVDD(void)
{
    // Configure UICR_REGOUT0 register only if it is set to default value.
    if ((NRF_UICR->REGOUT0 & UICR_REGOUT0_VOUT_Msk) ==
            (UICR_REGOUT0_VOUT_DEFAULT << UICR_REGOUT0_VOUT_Pos)) {
        NRF_NVMC->CONFIG = NVMC_CONFIG_WEN_Wen;
        while (NRF_NVMC->READY == NVMC_READY_READY_Busy) {}

        NRF_UICR->REGOUT0 = (NRF_UICR->REGOUT0 & ~((uint32_t)UICR_REGOUT0_VOUT_Msk)) |
                            (UICR_REGOUT0_VOUT_3V3 << UICR_REGOUT0_VOUT_Pos);

        NRF_NVMC->CONFIG = NVMC_CONFIG_WEN_Ren;
        while (NRF_NVMC->READY == NVMC_READY_READY_Busy) {}

        // System reset is needed to update UICR registers.
        NVIC_SystemReset();
    }
}

void LoRaPacketReceived(void)
{
    Serial.println("[SX1262] Got packet");

    size_t len = radio.getPacketLength();
    Serial.print("[SX1262] packet len:");
    Serial.println(len);

    unsigned char packet[256];
    int state = radio.readData(packet,len);
    for (int j = 0; j < len; j++)
        Serial.println(packet[j]);

    // Put the chip back in receive mode.
    radio.startReceive();
}

void setupLoRa() {
    rfPort = new SPIClass(
        /*SPIPORT*/NRF_SPIM3,
        /*MISO*/ LoRa_Miso,
        /*SCLK*/LoRa_Sclk,
        /*MOSI*/LoRa_Mosi);
    rfPort->begin();

    SPISettings spiSettings;

    radio = new Module(LoRa_Cs, LoRa_Dio1, LoRa_Rst, LoRa_Busy, *rfPort, spiSettings);

    SerialMon.print("[SX1262] Initializing ...  ");
    int state = radio.begin(869.5);
    if (state != ERR_NONE) {
        SerialMon.print("[SX1262] Initialization failed: ");
        SerialMon.println(state);
    } else {
        SerialMon.println("[SX1262] Initialization succeeded.");
        radio.setOutputPower(10);
        radio.setSyncWord(0x12);
        radio.setBandwidth(250.0);
        radio.setSpreadingFactor(12);
        radio.setCodingRate(8);
        radio.setPreambleLength(12);
        radio.setCRC(true);
        //radio.setTCXO(2.4);
        
        radio.setCurrentLimit(80);
        radio.setDio1Action(LoRaPacketReceived);
        radio.standby();
        radio.startReceive();
    }
}

void boardInit()
{

    uint8_t rlst = 0;

#ifdef HIGH_VOLTAGE
    configVDD();
#endif

    SerialMon.begin(MONITOR_SPEED);
    // delay(5000);
    // while (!SerialMon);
    SerialMon.println("Start\n");

    uint32_t reset_reason;
    sd_power_reset_reason_get(&reset_reason);
    SerialMon.print("sd_power_reset_reason_get:");
    SerialMon.println(reset_reason, HEX);

    pinMode(Power_Enable_Pin, OUTPUT);
    digitalWrite(Power_Enable_Pin, HIGH);

    pinMode(ePaper_Backlight, OUTPUT);
    //enableBacklight(true); //ON backlight
    enableBacklight(false); //OFF  backlight

    pinMode(GreenLed_Pin, OUTPUT);
    pinMode(RedLed_Pin, OUTPUT);
    pinMode(BlueLed_Pin, OUTPUT);

    pinMode(UserButton_Pin, INPUT_PULLUP);
    pinMode(Touch_Pin, INPUT_PULLUP);

    
    digitalWrite(GreenLed_Pin, HIGH);
    digitalWrite(RedLed_Pin, HIGH);
    digitalWrite(BlueLed_Pin, HIGH);

    setupDisplay();
    // setupLoRa();
}
