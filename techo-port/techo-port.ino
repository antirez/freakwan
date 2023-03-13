#include <SPI.h>
#include <Wire.h>

#include "hwconfig.h"
#include "eink.h"
#include "radio.h"

void configVDD(void);
void boardInit();

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

    digitalWrite(BlueLed_Pin, HIGH);
    delay(50);
    digitalWrite(GreenLed_Pin, LOW);
    uint8_t packet[256];
    float rssi;
    size_t len = PacketsQueueGet(packet, &rssi);
    if (len) protoProcessPacket(packet,len,rssi);

    SerialMon.print("Looping: ");
    SerialMon.println(total_loops);
    if (total_loops++ == 10000) NRFDeepSleep();
}

void boardInit()
{

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
}
