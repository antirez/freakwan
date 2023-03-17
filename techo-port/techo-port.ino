/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#include <SPI.h>
#include <Wire.h>

#include "hwconfig.h"
#include "eink.h"
#include "radio.h"
#include "ble.h"
#include "settings.h"

struct FreakWANGlobalSettings FW;

/* Go into deep sleep. */
void NRFDeepSleep(void) {
    NRF_POWER->SYSTEMOFF = 1;
}

#define TICK_DUR 50
#define MS_TO_TICKS(ms) ((ms)/TICK_DUR)
void loop() {
    static int ticks = 0;

    digitalWrite(GreenLed_Pin, HIGH);
    delay(TICK_DUR-1);
    digitalWrite(GreenLed_Pin, LOW);
    delay(1);

    /* Process incoming LoRa packets. */
    uint8_t packet[256];
    float rssi;
    size_t len;
    while((len = receiveLoRaPacket(packet, &rssi)) != 0)
        protoProcessPacket(packet,len,rssi);

    /* Send packets from the queue. */
    processLoRaSendQueue();

    /* Process commands from BLU UART. */
    BLEProcessCommands();

    if (!(ticks % MS_TO_TICKS(5000))) {
        char buf[128];
        int free_memory = dbgHeapTotal()-dbgHeapUsed();
        snprintf(buf,sizeof(buf),"~%s, FreeMem:%d, SendQueueLen:%d",
            FW.nick,free_memory,getLoRaSendQueueLen());
        SerialMon.println(buf);
    }

    if (!(ticks % MS_TO_TICKS(10000))) {
        static int hicount = 0;
        char msg[32];
        snprintf(msg,sizeof(msg),"Hi %d",hicount);
        protoSendDataMessage(FW.nick,msg,strlen(msg),0);
        hicount++;
    }

    if (ticks >= MS_TO_TICKS(600*1000)) {
        digitalWrite(GreenLed_Pin, HIGH);
        NRFDeepSleep();
    }

    ticks++;
}

/* ================================ Initialization ========================== */

/* Create a human readable random nickname for the device using
 * the device unique ID. */
void setRandomNick(char *s, size_t len) {
    const char consonants[] = "kvprmnzflst";
    const char vowels[] = "aeiou";
    if (len == 0) return;
    len--; // Make space for null term.
    int nicklen = 8;
    uint32_t val = NRF_FICR->DEVICEID[0];
    while(len-- && nicklen--) {
        if (nicklen & 1) {
            *s = vowels[val%(sizeof(vowels)-1)];
            val /= (sizeof(vowels)-1);
        } else {
            *s = consonants[val%(sizeof(consonants)-1)];
            val /= (sizeof(consonants)-1);
        }
        s++;
    }
    *s = 0;
}

void initGlobalConfig(void) {
    FW.lora_freq = 869.5;
    FW.lora_sp = 12;
    FW.lora_cr = 8;
    FW.lora_bw = 250;
    FW.lora_tx_power = 10;
    setRandomNick(FW.nick,sizeof(FW.nick));
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

void setup() {
    initGlobalConfig();
    Serial.begin(115200);
    delay(200);
    boardInit();
    delay(200);
    displayPrint("FreakWAN started");
}
