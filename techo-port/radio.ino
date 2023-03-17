/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#include <RadioLib.h>
#include "utils.h"

/* ============================ Data structures ============================= */

/* Packets are written by the IRQ handler of the LoRa chip event
 * into the packets queue. But they are also accessed from the normal
 * program flow in order to process them. The IRQ will fill the following
 * pre-allocated (global) indexed structure, and the main task will
 * fetch data periodically. */

#define QUEUE_MAX_LEN 8 // Use a power of 2 to optimized modulo operation.

struct DataPacket {
    struct DataPacket *next;    // Next packet in queue.
    float rssi;                 // Received packet RSSI
    uint8_t len;                // Packet len
    uint8_t bad_crc;            // CRC mismatch if non zero.
    uint8_t packet[0];          // Packet bytes
};

/* We push packets to the tail, and fetch from the head, so this
 * queue is a FIFO. */
struct PacketsQueue {
    unsigned int len;           // Queue len.
    DataPacket *head, *tail;
};

enum RadioStates {
    RadioStateStandby,
    RadioStateRx,
    RadioStateTx,
    RadioStateSleep
};

/* ============================== Global state ============================== */

struct PacketsQueue *RXQueue;   // Queue of received packets.
struct PacketsQueue *TXQueue;   // Queue of packets to transmit.
SX1262 radio = nullptr;         // LoRa radio object
RadioStates RadioState = RadioStateStandby;
volatile unsigned long PreambleStartTime = 0;

/* RxDone, PreambleDetected, Timeout, CrcErr, HeaderErr. */
uint16_t RadioIRQMask = 0b0000001001100111;

/* ============================== Implementation ============================ */

/* Create a new queue. */
struct PacketsQueue *createPacketsQueue(void) {
    struct PacketsQueue *q = (struct PacketsQueue*) malloc(sizeof(*q));
    q->len = 0;
    q->head = NULL;
    q->tail = NULL;
    return q;
}

/* Add a packet to the packets queue. Should be called only from the LoRa
 * chip IRQ, since does not disable interrupts. To call it from elsewhere
 * protect the call with noInterrupts() / interrupts(). */
void packetsQueueAdd(struct PacketsQueue *q, uint8_t *packet, size_t len, float rssi, int bad_crc) {
    struct DataPacket *p = (struct DataPacket*) malloc(sizeof(*p)+len);
    memcpy(p->packet,packet,len);
    p->len = len;
    p->rssi = rssi;
    p->next = NULL;
    p->bad_crc = bad_crc;
    if (q->len == 0) {
        q->tail = p;
        q->head = p;
    } else {
        q->tail->next = p;
        q->tail = p;
    }
    q->len++;
}

/* Fetch the oldest packet inside the queue, if any. Freeing the packet
 * once no longer used is up to the caller. */
struct DataPacket *packetsQueueGet(PacketsQueue *q) {
    if (q->len == 0) return NULL;
    struct DataPacket *p = q->head;
    q->head = p->next;
    q->len--;
    if (q->len == 0) {
        q->head = NULL;
        q->tail = NULL;
    }
    return p;
}

/* IRQ handler of the LoRa chip. Called when the current operation was
 * completed (either packet received or transmitted). */
void LoRaIRQHandler(void) {
    int status = radio.getIrqStatus();

    Serial.print("IRQ ");
    Serial.println(status,BIN);
    if (status & RADIOLIB_SX126X_IRQ_RX_DONE) {
        uint8_t packet[256];
        size_t len = radio.getPacketLength();
        int state = radio.readData(packet,len);
        float rssi = radio.getRSSI();
        int bad_crc = (status & RADIOLIB_SX126X_IRQ_CRC_ERR) != 0;

        packetsQueueAdd(RXQueue,packet,len,rssi,bad_crc);
    } else if (status & RADIOLIB_SX126X_IRQ_TX_DONE) {
        RadioState = RadioStateRx;
    }

    /* In order to know if the radio is busy receiving, and avoid starting
     * a transmission while a packet is on the air, we remember if we
     * are receiving some packet right now, and at which time the
     * preamble started. */
    if (status & 0b100 /* Preamble detected. */) {
        Serial.println("Preamble detected");
        PreambleStartTime = millis();
    } else {
        /* For any other event, that is packet received, packet error and
         * so forth, we want to reset the variable to report we
         * are no longer receiving a packet. */
        PreambleStartTime = 0;
    }

    // Put the chip back in receive mode.
    radio.startReceive(RADIOLIB_SX126X_RX_TIMEOUT_INF,RadioIRQMask,RadioIRQMask);
} /* Return true if we are currently in the process of receiving a packet. */
#define MAX_TIME_ON_AIR 2000
bool packetOnAir(void) {
    if (PreambleStartTime == 0) return false;
    /* We need to reset the state after a given amount of time. Unfortunately
     * while the SX1276 has a status register that will tell us if somebody
     * is transmitting a LoRa packet right now, with the SX1262 there is
     * no way to know this while receiving a packet. Because of this, sometimes,
     * the radio picks a preamble about a packet that is not really fully
     * received, or for which the sync word is different than the one we
     * configured: in this case the RX Done IRQ event will never fire, and the
     * PreambleStartTime condition will remain true. This is why we use a
     * timeout and clear the state after it elapsed. */
    if (timeElapsedSince(PreambleStartTime) > MAX_TIME_ON_AIR) {
        PreambleStartTime = 0;
        return false;
    } else {
        return true;
    }
}

/* =============================== Exported API ============================= */

/* This is the exported API to get packets that arrived via the LoRa
 * RF link. */
size_t receiveLoRaPacket(uint8_t *packet, float *rssi) {
    /* Disable interrupts since the LoRa radio interrupt is the one
     * writes packets to the same queue we are accessing here. */
    noInterrupts();
    struct DataPacket *p = packetsQueueGet(RXQueue);
    interrupts();
    size_t retval = 0;
    if (p) {
        retval = p->len;
        memcpy(packet,p->packet,p->len);
        *rssi = p->rssi;
        free(p);
    }
    return retval;
}

/* Put the packet in the send queue. Will actually send it in
 * ProcessLoRaSendQueue(). */
#define TX_QUEUE_MAX_LEN 128
void sendLoRaPacket(uint8_t *packet, size_t len) {
    if (len > 256) {
        Serial.println("[LoRa] too long packet discarded by SendLoRaPacket()");
        return;
    }
    if (TXQueue->len == TX_QUEUE_MAX_LEN) {
        struct DataPacket *oldest = packetsQueueGet(TXQueue);
        free(oldest);
        Serial.println("[LoRa] WARNING: TX queue overrun. "
                       "Old packet discarded.");
    }
    packetsQueueAdd(TXQueue,packet,len,0,0);
}

/* Try to send the next packet in queue, if */
void processLoRaSendQueue(void) {
    if (RadioState == RadioStateTx) return; /* Already transmitting. */
    if (packetOnAir()) {
        SerialMon.println("[SX1262] channel busy");
        return;              /* Channel is busy. */
    }

    struct DataPacket *p = packetsQueueGet(TXQueue);
    if (p) {
        SerialMon.println("[SX1262] sending packet");
        RadioState = RadioStateTx;
        radio.startTransmit(p->packet,p->len);
        free(p);
    }
}

/* Return the number of packets waiting to be sent. */
int getLoRaSendQueueLen(void) {
    return TXQueue->len;
}

void setLoRaParams(void) {
    radio.standby(); // Configuration should be modified in standby.
    radio.setFrequency(FW.lora_freq);
    radio.setBandwidth(FW.lora_bw);
    radio.setSpreadingFactor(FW.lora_sp);
    radio.setCodingRate(FW.lora_cr);
    radio.setOutputPower(FW.lora_tx_power);
    radio.setCurrentLimit(80);
    radio.setDio1Action(LoRaIRQHandler);
}

/* ============================== Initialization ============================ */

void setupLoRa(void) {
    RXQueue = createPacketsQueue();
    TXQueue = createPacketsQueue();

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
        radio.setSyncWord(0x12);
        radio.setPreambleLength(12);
        radio.setCRC(true);
        radio.setRxBoostedGainMode(RADIOLIB_SX126X_RX_GAIN_BOOSTED,true);
        setLoRaParams();
        //radio.setTCXO(2.4);
        RadioState = RadioStateRx;
        radio.startReceive(RADIOLIB_SX126X_RX_TIMEOUT_INF,RadioIRQMask,RadioIRQMask);
    }
}
