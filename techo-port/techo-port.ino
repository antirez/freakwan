#include <SPI.h>
#include <Wire.h>

#include "hwconfig.h"
#include "eink.h"
#include "radio.h"
#include "ble.h"
#include "settings.h"

struct FreakWANGlobalSettings FW;

void boardInit();

void setup() {
    initGlobalConfig();
    Serial.begin(115200);
    delay(200);
    boardInit();
    delay(200);
    displayPrint("FreakWAN started");
}

void initGlobalConfig(void) {
    FW.lora_freq = 869.5;
    FW.lora_sp = 12;
    FW.lora_cr = 8;
    FW.lora_bw = 250;
    FW.lora_tx_power = 10;
}

/* Go into deep sleep. */
void NRFDeepSleep(void) {
    NRF_POWER->SYSTEMOFF = 1;
}

void loop() {
    static int ticks = 0;

    digitalWrite(GreenLed_Pin, HIGH);
    delay(45);
    digitalWrite(GreenLed_Pin, LOW);
    delay(5);
    uint8_t packet[256];
    float rssi;

    /* Process incoming LoRa packets. */
    while(1) {
        size_t len = PacketsQueueGet(packet, &rssi);
        if (len)
            protoProcessPacket(packet,len,rssi);
        else
            break;
    }

    /* Process commands from BLU UART. */
    BLEProcessCommands();

    if (!(ticks % 10)) {
        SerialMon.print("Looping: ");
        SerialMon.println(ticks);
    }

    if (ticks == 50000) {
        digitalWrite(GreenLed_Pin, HIGH);
        NRFDeepSleep();
    }

    ticks++;
}

void boardInit() {
    uint8_t rlst = 0;

    SerialMon.begin(MONITOR_SPEED);

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

    // Make sure all the leds are off at start-up
    digitalWrite(GreenLed_Pin, HIGH);
    digitalWrite(RedLed_Pin, HIGH);
    digitalWrite(BlueLed_Pin, HIGH);

    setupDisplay();
    setupLoRa();
    setupBLE();
}
