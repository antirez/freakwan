#include <RadioLib.h>

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
void PacketsQueueAdd(struct PacketsQueue *q, uint8_t *packet, size_t len, float rssi) {
    struct DataPacket *p = (struct DataPacket*) malloc(sizeof(*p)+len);
    memcpy(p->packet,packet,len);
    p->len = len;
    p->rssi = rssi;
    p->next = NULL;
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
struct DataPacket *PacketsQueueGet(PacketsQueue *q) {
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

/* This is the exported API to get packets that arrived via the LoRa
 * RF link. */
size_t ReceiveLoRaPacket(uint8_t *packet, float *rssi) {
    /* Disable interrupts since the LoRa radio interrupt is the one
     * writes packets to the same queue we are accessing here. */
    noInterrupts();
    struct DataPacket *p = PacketsQueueGet(RXQueue);
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

/* IRQ handler of the LoRa chip. Called when the current operation was
 * completed (either packet received or transmitted). */
void LoRaPacketReceived(void) {
    uint8_t packet[256];
    size_t len = radio.getPacketLength();
    int state = radio.readData(packet,len);
    float rssi = radio.getRSSI();

    PacketsQueueAdd(RXQueue,packet,len,rssi);
    
    // Put the chip back in receive mode.
    radio.startReceive();
}

void setLoRaParams(void) {
    radio.standby(); // Configuration should be modified in standby.
    radio.setFrequency(FW.lora_freq);
    radio.setBandwidth(FW.lora_bw);
    radio.setSpreadingFactor(FW.lora_sp);
    radio.setCodingRate(FW.lora_cr);
    radio.setOutputPower(FW.lora_tx_power);
    radio.setCurrentLimit(80);
    radio.setDio1Action(LoRaPacketReceived);
}

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
        radio.startReceive();
    }
}
