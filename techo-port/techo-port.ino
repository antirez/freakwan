#include <SPI.h>
#include <Wire.h>
#include <RadioLib.h>

#include "hwconfig.h"
#include "eink.h"
#include "proto.h"

void configVDD(void);
void boardInit();
void setupLoRa();

SX1262          radio     = nullptr;        // LoRa radio object

uint32_t        blinkMillis = 0;
uint8_t rgb = 0;

void setup() {
    Serial.begin(115200);
    delay(200);
    boardInit();
    delay(200);
    displayPrint("FreakWAN started");
}

/* Go into deep sleep. */
void NRFDeepSleep(void) {
    NRF_POWER->SYSTEMOFF = 1;
}

void loop() {
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

        if (total_loops++ == 10000) NRFDeepSleep();
    }
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

    protoProcessPacket(packet,len);

    // Put the chip back in receive mode.
    radio.startReceive();
}

void setupLoRa() {
    SPIClass *rfPort = new SPIClass(
        /*SPIPORT*/NRF_SPIM3,
        /*MISO*/ LoRa_Miso,
        /*SCLK*/LoRa_Sclk,
        /*MOSI*/LoRa_Mosi);
    rfPort->begin();

    SPISettings spiSettings;

    radio = new Module(LoRa_Cs, LoRa_Dio1, LoRa_Rst, LoRa_Busy, *rfPort, spiSettings);

    SerialMon.print("[SX1262] Initializing ...  ");
    int state = radio.begin(869.5);
    if (state != RADIOLIB_ERR_NONE) {
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
        radio.setRxBoostedGainMode(RADIOLIB_SX126X_RX_GAIN_BOOSTED,true);
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
    setDisplayBacklight(false);

    pinMode(GreenLed_Pin, OUTPUT);
    pinMode(RedLed_Pin, OUTPUT);
    pinMode(BlueLed_Pin, OUTPUT);

    pinMode(UserButton_Pin, INPUT_PULLUP);
    pinMode(Touch_Pin, INPUT_PULLUP);

    // Make sure all teh leds are off at start-up
    digitalWrite(GreenLed_Pin, LOW);
    digitalWrite(RedLed_Pin, LOW);
    digitalWrite(BlueLed_Pin, LOW);

    setupDisplay();
    setupLoRa();
}
