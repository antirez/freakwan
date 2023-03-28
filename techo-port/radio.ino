/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#define RADIOLIB_GODMODE
#include <RadioLib.h>
#include "utils.h"
#include "log.h"

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
    unsigned long tx_time;      // Time at which transmit the packet (0 = ASAP).
    uint8_t tx_num;             // How many times to retransmit the packet.
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

/* Variables used to detect "busy channel" condition for Listen Before Talk. */
volatile unsigned long PreambleStartTime = 0;
volatile bool ValidHeaderFound = false;

/* IRQ mask:
 * Bit 0 TxDone,
 * Bit 1 RxDone,
 * Bit 2 PreambleDetected
 * Bit 3 (not used by LoRa)
 * Bit 4 HeaderValid
 * Bit 5 HeaderErr
 * Bit 6 CrcErr
 */
uint16_t RadioIRQMask = 0b1110111;

/* ============================== Implementation ============================ */

/* Create a new queue. */
struct PacketsQueue *createPacketsQueue(void) {
    struct PacketsQueue *q = (struct PacketsQueue*) malloc(sizeof(*q));
    q->len = 0;
    q->head = NULL;
    q->tail = NULL;
    return q;
}

/* Low level function to add an already allocated packet to a queue.
 * Warning: the RXQueue is handled by the interrupt, so make sure to
 * protect access disabling interrupts if you want to access it from
 * other sections. */
struct DataPacket *packetsQueueAdd(struct PacketsQueue *q, struct DataPacket *p) {
    if (q->len == 0) {
        q->tail = p;
        q->head = p;
    } else {
        q->tail->next = p;
        q->tail = p;
    }
    q->len++;
    return p;
}

/* Allocate and add a packet to the packets queue. If the target is the
 * RX queue, this function should be called only from the LoRa chip IRQ, since
 * does not disable interrupts. To call it from elsewhere protect the call
 * with noInterrupts() / interrupts(). */
struct DataPacket *packetsQueueAddPacket(struct PacketsQueue *q, uint8_t *packet, size_t len, float rssi, int bad_crc) {
    struct DataPacket *p = (struct DataPacket*) malloc(sizeof(*p)+len);
    memcpy(p->packet,packet,len);
    p->tx_time = 0; // ASAP by default.
    p->tx_num = 1;  // Just once by default.
    p->len = len;
    p->rssi = rssi;
    p->next = NULL;
    p->bad_crc = bad_crc;
    return packetsQueueAdd(q,p);
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

/* Return the length of the queue. */
unsigned int packetsQueueLength(PacketsQueue *q) {
    return q->len;
}

/* IRQ handler of the LoRa chip. Called when the current operation was
 * completed (either packet received or transmitted).
 *
 * Note that inside the IRQ it is not safe to write to the serial (via the
 * fwLog() calls), however this is disabled by default, and is only used
 * for debugging. */
void LoRaIRQHandler(void) {
    int status = radio.getIrqStatus();

    if (status & RADIOLIB_SX126X_IRQ_RX_DONE) {
        fwLog("D:RX done");
        uint8_t packet[256];
        size_t len = radio.getPacketLength();
        int state = radio.readBuffer(packet,len);
        float rssi = radio.getRSSI();
        int bad_crc = (status & RADIOLIB_SX126X_IRQ_CRC_ERR) != 0;

        packetsQueueAddPacket(RXQueue,packet,len,rssi,bad_crc);

        /* Reset the SX1262 state to receive the next packet: note that
         * it will stay in RX mode, since we initialized the chip with
         * "infinite" timeout. */
        radio.setBufferBaseAddress();
        PreambleStartTime = 0;
        ValidHeaderFound = false;
    } else if (status & RADIOLIB_SX126X_IRQ_TX_DONE) {
        fwLog("D:TX done");
        digitalWrite(RedLed_Pin, HIGH);
        RadioState = RadioStateRx;
        // Put the chip back in receive mode.
        radio.startReceive(RADIOLIB_SX126X_RX_TIMEOUT_INF,RadioIRQMask,RadioIRQMask);
        PreambleStartTime = 0;
        ValidHeaderFound = false;
    } else if (status & 0b100 /* Preamble detected. */) {
        /* In order to know if the radio is busy receiving, and avoid starting
         * a transmission while a packet is on the air, we remember if we
         * are receiving some packet right now, and at which time the
         * preamble started. */
        fwLog("D:Preamble detected");
        PreambleStartTime = millis();
        ValidHeaderFound = false;
    } else if (status & 0b10000 /* Valid Header. */) {
        /* After the preamble, the LoRa radio may also detect that the
         * packet has a good looking header. We set this state, since, 
         * in this case, we are willing to wait for a larger timeout to
         * clear the radio busy condition: we hope we will receive the
         * RX DONE event, and set PreambleStartTime to zero again. */
        fwLog("D:Valid header found");
        ValidHeaderFound = true;
    } else {
        /* Header error event. Clear the packet on air state. */
        fwLog("D:Bad header");
        PreambleStartTime = 0;
        ValidHeaderFound = false;
        radio.clearIrqStatus();
        radio.setBufferBaseAddress();
    }
    radio.clearIrqStatus();
}

/* Return true if we are currently in the process of receiving a packet. */
#define MAX_TIME_ON_AIR_NO_SYNC 2000
#define MAX_TIME_ON_AIR_SYNC 5000
bool packetOnAir(void) {
    if (PreambleStartTime == 0) return false;
    /* In theory, the channel busy condition provided by the PreambleStartTime
     * variable should clear automatically, once the RX is done. However
     * things are a bit harder: sometimes we just detect a preamble, but the
     * sync word is different, so the condition will never be cleared. For
     * this reason we take the busy state for a maximum amount of time:
     *
     * 1. If we received not just the preamble, but also the header, we
     *    can hope the RX done event will eventually fire, so we allow for
     *    a longer time before declaring anyway the channel as free.
     * 2. If we just received the preamble, not followed by a valid sync word,
     *    we will clear it faster.
     *
     * Note that with the SX1276, there is no such a problem that we have here
     * with the SX1262. The older chip has a status register that will tell
     * us if somebody is transmitting a LoRa packet right now. The register is
     * not implemented in the new chip. */
     unsigned long max_time = ValidHeaderFound ? MAX_TIME_ON_AIR_SYNC :
                                                 MAX_TIME_ON_AIR_NO_SYNC;
    if (timeElapsedSince(PreambleStartTime) > max_time) {
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
        fwLog("W:[LoRa] too long packet discarded by SendLoRaPacket()");
        return;
    }
    if (TXQueue->len == TX_QUEUE_MAX_LEN) {
        struct DataPacket *oldest = packetsQueueGet(TXQueue);
        free(oldest);
        fwLog("W:[LoRa] WARNING: TX queue overrun. Old packet discarded.");
    }
    packetsQueueAddPacket(TXQueue,packet,len,0,0);
}

/* Try to send the next packet in queue, if */
void processLoRaSendQueue(void) {
    if (RadioState == RadioStateTx) return; /* Already transmitting. */
    if (packetOnAir()) {
        fwLog("T:.");
        return; /* Channel is busy, we can't send. */
    }

    unsigned int len = packetsQueueLength(TXQueue);
    while (len--) {
        struct DataPacket *p = packetsQueueGet(TXQueue);
        if (!p) return; // Empty queue.

        if (p->tx_time == 0 || timeReached(p->tx_time)) {
            fwLog("V:[SX1262] sending packet");
            digitalWrite(RedLed_Pin, LOW);
            RadioState = RadioStateTx;
            radio.startTransmit(p->packet,p->len);
            /* Packet should be sent again? Add it back with modified
             * send time and tx number. */
            if (p->tx_num > 1) {
                p->tx_num--;
                p->tx_time = millisPlusRandom(3000,10000);
                packetsQueueAdd(TXQueue,p);
            } else {
                free(p);
            }
            return; // Now the radio is busy. Return ASAP.
        } else {
            // Send time not reached. At it back at the end of the FIFO. */
            packetsQueueAdd(TXQueue,p);
        }
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

    /* Put the radio back in RX mode, unless we were in standby
     * already. Note that even if we were transmitting when the
     * parameters changed, we want to go in RX mode, as anyway
     * the transmission was aborted as soon as we went into standby
     * mode to set the new parameters. */
    if (RadioState != RadioStateStandby) {
        radio.startReceive(RADIOLIB_SX126X_RX_TIMEOUT_INF,
            RadioIRQMask,RadioIRQMask);
        RadioState = RadioStateRx;
    }
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

    fwLog("V:[SX1262] Initializing ...");
    int state = radio.begin(869.5);
    if (state != RADIOLIB_ERR_NONE) {
        fwLog("W:[SX1262] Initialization failed: %d",state);
    } else {
        fwLog("V:[SX1262] Initialization succeeded.");
        radio.setSyncWord(0x12);
        radio.setPreambleLength(12);
        radio.setCRC(true);
        radio.setRxBoostedGainMode(RADIOLIB_SX126X_RX_GAIN_BOOSTED,true);
        RadioState = RadioStateRx;
        setLoRaParams();
        //radio.setTCXO(2.4);
    }
}
