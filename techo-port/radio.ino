#include <RadioLib.h>

/* Packets are written by the IRQ handler of the LoRa chip event
 * into the packets queue. But they are also accessed from the normal
 * program flow in order to process them. The IRQ will fill the following
 * pre-allocated (global) indexed structure, and the main task will
 * fetch data periodically. */

#define QUEUE_MAX_LEN 8 // Use a power of 2 to optimized modulo operation.

typedef struct PQPacket {
    float rssi;             // Received packet RSSI
    uint8_t len;            // Packet len
    uint8_t packet[256];    // Packet bytes
} PQPacket;

typedef struct PQ {
    unsigned int len;    // Queue len (used slots).
    unsigned int idx;    // Next packet to fill inside the 'packets' array.
    struct PQPacket packets[QUEUE_MAX_LEN];
} PQ;

PQ PacketsQueue;                // Our global queue;
SX1262 radio = nullptr;         // LoRa radio object

/* Add a packet to the packets queue. Should be called only from the LoRa
 * chip IRQ, since does not disable interrupts. To call it from elsewhere
 * protect the call with noInterrupts() / interrupts(). */
void PacketsQueueAdd(uint8_t *packet, size_t len, float rssi) {
    PQ *q = &PacketsQueue;
    PQPacket *p;

    p = q->packets+q->idx;
    memcpy(p->packet,packet,len);
    p->len = len;
    p->rssi = rssi;
    q->idx = (q->idx+1) % QUEUE_MAX_LEN;
    if (q->len < QUEUE_MAX_LEN) q->len++;
}

/* Fetch the oldest packet inside the queue, if any. Populate data by
 * reference and return the packet length. If the queue is empty, zero
 * is returned. */
size_t PacketsQueueGet(uint8_t *packet, float *rssi) {
    PQ *q = &PacketsQueue;
    noInterrupts();
    if (q->len == 0) {
        interrupts();
        return 0;
    }
    unsigned int idx = (q->idx + QUEUE_MAX_LEN - q->len) % QUEUE_MAX_LEN;
    int len = q->packets[idx].len;
    memcpy(packet,q->packets[idx].packet,len);
    *rssi = q->packets[idx].rssi;
    q->len--;
    interrupts();
    return len;
}

/* IRQ handler of the LoRa chip. Called when the current operation was
 * completed (either packet received or transmitted). */
void LoRaPacketReceived(void) {
    uint8_t packet[256];
    size_t len = radio.getPacketLength();
    int state = radio.readData(packet,len);
    float rssi = radio.getRSSI();

    PacketsQueueAdd(packet,len,rssi);
    
    // Put the chip back in receive mode.
    radio.startReceive();
}

void setupLoRa(void) {
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
