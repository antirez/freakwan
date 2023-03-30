/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#include <stdint.h>
#include "proto.h"
#include "eink.h"
#include "radio.h"
#include "ble.h"
#include "rax.h"

#define MSG_FLAG_RELAYED (1<<0)
#define MSG_FLAG_PLEASE_RELAY (1<<1)
#define MSG_FLAG_FRAGMENT (1<<2)
#define MSG_FLAG_MEDIA (1<<3)
#define MSG_FLAG_ENCR (1<<4)

#define MSG_TYPE_DATA 0
#define MSG_TYPE_ACK 1
#define MSG_TYPE_HELLO 2
#define MSG_TYPE_BULK_START 3
#define MSG_TYPE_BULK_DATA 4
#define MSG_TYPE_BULK_END 5
#define MSG_TYPE_BULK_REPLY 6

#define MSG_ID_LEN 4
#define SENDER_ID_LEN 6

/* To work properly, a device is required to avoid processing messages multiple
 * times. This is useful because FreakWAN messages can be retransmitted and
 * relayed multiple times. The way the receiver knows that a message was
 * already processed, is by using the fact each message has a random 32 bit
 * message ID stored inside the header. In the C implementation of the FreakWAN
 * protocol, we use just a fixed length hash table of 512 entries, where new
 * entries (of processed messages IDs) replace the old ones, and there is never
 * any cleanup.
 *
 * In the following table of 512 messages, each message ID is stored at
 * offset INDEX*4, where the INDEX is computed as the XOR of all the
 * four bytes of the message ID, taking the first two bytes shifted on
 * the left by 1 bit (in order to have a 9 bits output).
 *
 * Note that while very efficient, this approach has two limitations:
 * 1. Two messages sent at a near time may have colliding message IDs.
 *    In this case messages could be reprocessed. However there is only
 *    0.2% of probability of this happening with two messages, and the
 *    effects are not so bad.
 * 2. Another issue is that entries are never cleaned up, so it is possible
 *    that a message sent much later in time, having the same message ID
 *    of a seen message, is not processed at all. This is even less likely
 *    because if we consider a full table of 512 random messages, the
 *    probability of a message being already inside is only 0.00001%.
 */
char MessageCache[512*MSG_ID_LEN] = {0};

/* FreakWAN protocol message structure. */
struct Message {
    /* Common header */
    uint8_t type;       // Packet type.
    uint8_t flags;      // Packet flags.
    
    /* Type specifid header. */
    union {
        struct {
            uint8_t id[MSG_ID_LEN]; // Message ID.
            uint8_t ttl;    // Time to live.
            uint8_t sender[SENDER_ID_LEN]; // Sender address.
            uint8_t nicklen;    // Nick length.
            uint8_t payload[0]; // Nick + text.
        } data;
        struct {
            uint8_t id[MSG_ID_LEN]; // Message ID.
            uint8_t ack_type;       // Type of the acknowledged message.
            uint8_t sender[SENDER_ID_LEN]; // Sender address.
        } ack;
        struct {
            uint8_t sender[SENDER_ID_LEN]; // Sender address.
            uint8_t seen;       // Number of other nodes sensed.
            uint8_t nicklen;    // Nick length.
            uint8_t payload[0]; // Nick + text.
        } hello;
    };
};

/* Thanks to hello messages, we are able to sense nearby nodes.
 * We save the recognized nodes in a table, and each node is
 * described by the following structure. */

struct Neighbor {
    float rssi;                 // RSSI of the last HELLO message.
    unsigned long last_seen_time; // In milliseconds time.
    uint8_t seen;               // Number of nodes this node can receive.
    uint8_t id[SENDER_ID_LEN];  // Node ID.
    char *nick;                 // Nickname.
    char *status;               // Status message in the last HELLO message.
};

struct rax *Neighbors = NULL;

/* Called by FreakWAN main initialization function. */
void protoInit(void) {
    Neighbors = raxNew();
}

/* Called periodically by FreakWAN main loop. */
void protoCron(void) {
    /* TODO:
     * 1. Scan the Neighbors list to cleanup too old nodes.
     * 2. Send HELLO messages if not in quiet mode. */
}

/* Return the number of known nodes. */
size_t protoGetNeighborsCount(void) {
    return raxSize(Neighbors);
}

/* ============================== Prototypss ================================ */

static void protoSendACK(uint8_t *msgid, int ack_type);

/* ========================== Neighbors handling ============================ */

/* Free an heap allocated Neighboor structure. */
void neighborFree(struct Neighbor *n) {
    free(n->nick);
    free(n->status);
    free(n);
}

/* Add a neighbor to our table of sensed nodes (via HELLO messages).
 * If the node was already in the table 0 is returned, otherwise
 * the function returns 1. As a side effect, the table is populated or
 * the existing node is updated. */
#define MAX_NEIGHBORS 128 // Avoid OOM attack.
int neighborAdd(uint8_t *nodeid, const char *nick, size_t nick_len,
                                 const char *status, size_t status_len,
                                 float rssi, int seen)
{
    if (raxSize(Neighbors) > MAX_NEIGHBORS) return 0;
    struct Neighbor *n;
    int newnode = 0;

    /* Check if this node is already in the table. */
    n = (struct Neighbor*) raxFind(Neighbors,nodeid,SENDER_ID_LEN);
    if (n == raxNotFound) {
        newnode = 1;
        n = (struct Neighbor*) malloc(sizeof(*n));
        if (!n) return 0;
        n->nick = NULL;
        n->status = NULL;
        raxInsert(Neighbors,nodeid,SENDER_ID_LEN,n,NULL);
    }

    /* Update fields we set both for new and known nodes. */
    n->rssi = rssi;
    n->seen = seen;
    n->last_seen_time = millis();

    free(n->nick);
    free(n->status);
    n->nick = (char*)malloc(nick_len+1);
    n->status = (char*)malloc(status_len+1);
    if (!n->nick || !n->status) {
        /* Out of memory setting the string fields. */
        neighborFree(n);
        raxRemove(Neighbors,nodeid,SENDER_ID_LEN,NULL);
    } else {
        memcpy(n->nick,nick,nick_len);
        memcpy(n->status,status,status_len);
        n->nick[nick_len] = 0;
        n->status[status_len] = 0;
    }
    return newnode;
}

/* ============================ Messages cache ============================== */

/* Given the message ID, return the index in the message cache table. */
static unsigned int messageCacheHash(uint8_t *mid) {
    return (mid[0]<<1) ^ (mid[1]<<1) ^ mid[2] ^ mid[3];
}

/* Add the message ID into the message cache. */
static void messageCacheAdd(uint8_t *mid) {
    unsigned int offset = messageCacheHash(mid)*MSG_ID_LEN;
    memcpy(MessageCache+offset,mid,MSG_ID_LEN);
}

/* Look for the message ID in the message cache. Returns 1 if the ID
 * is found, otherwise 0. */
static int messageCacheFind(uint8_t *mid) {
    unsigned int offset = messageCacheHash(mid)*MSG_ID_LEN;
    return memcmp(MessageCache+offset,mid,MSG_ID_LEN) == 0;
}

/* ========================== Messages processing =========================== */

void protoProcessPacket(const unsigned char *packet, size_t len, float rssi) {
    struct Message *m = (struct Message*) packet;
    if (len < 2) return;    // No room for commmon header.

    /* Process data packet. */
    if (m->type == MSG_TYPE_DATA) {
        if (len < 14) return;   // No room for DATA header.
        if (14+m->data.nicklen > len) return; // Invalid nick len

        /* Was the message already processed? */
        if (messageCacheFind(m->data.id)) return;
        messageCacheAdd(m->data.id);
        if (!FW.quiet) protoSendACK(m->data.id,m->type);

        char buf[256+32];
        snprintf(buf,sizeof(buf),"%.*s> %.*s (rssi: %02.f)",(int)m->data.nicklen,m->data.payload,(int)len-14-m->data.nicklen,m->data.payload+m->data.nicklen,(double)rssi);
        displayPrint(buf);
        BLEReply(buf);
    } else if (m->type == MSG_TYPE_HELLO) {
        if (len < 10) return;   // No room for HELLO header.
        if (10+m->hello.nicklen > len) return; // Invalid nick len
        if (neighborAdd(m->hello.sender,
            (const char*)m->hello.payload,
            m->hello.nicklen,
            (const char*)m->hello.payload + m->hello.nicklen,
            len-10-m->hello.nicklen,
            rssi, m->hello.seen))
        {
            fwLog("[LoRa] New node sensed: %02x%02x%02x%02x%02x%02x",
                m->hello.sender[0], m->hello.sender[1], m->hello.sender[2],
                m->hello.sender[3], m->hello.sender[4], m->hello.sender[5]);
        }
    }
}

/* ============================ Messages sending ============================ */

/* Write six bytes of the device ID to the target string. */
static void protoFillSenderAddress(uint8_t *sender) {
    uint32_t id0 = NRF_FICR->DEVICEID[0];
    uint32_t id1 = NRF_FICR->DEVICEID[1];
    sender[0] = id0 & 0xff;
    sender[1] = (id0 >> 8) & 0xff;
    sender[2] = (id0 >> 16) & 0xff;
    sender[3] = (id0 >> 24) & 0xff;
    sender[4] = id1 & 0xff;
    sender[5] = (id1 >> 8) & 0xff;
}

/* Send a data message with the specified nick, message and flags. */
void protoSendDataMessage(const char *nick, const char *msg, size_t msglen, uint8_t flags) {
    unsigned char buf[256];
    struct Message *m = (struct Message*) buf;
    int nicklen = strlen(nick);
    int hdrlen = 14; /* Data header + 1 nick len byte. */

    /* Trim nick and len to never go over max packet size. */
    if (hdrlen+nicklen > sizeof(buf))
        nicklen = sizeof(buf)-hdrlen;
    if (hdrlen+nicklen+msglen > sizeof(buf))
        msglen = sizeof(buf)-hdrlen-nicklen;

    m->type = MSG_TYPE_DATA;
    m->flags = flags;
    m->data.id[0] = random(256);
    m->data.id[1] = random(256);
    m->data.id[2] = random(256);
    m->data.id[3] = random(256);
    m->data.ttl = 15;
    protoFillSenderAddress(m->data.sender);
    m->data.nicklen = nicklen;
    memcpy(m->data.payload,nick,m->data.nicklen);
    memcpy(m->data.payload+m->data.nicklen,msg,msglen);
    sendLoRaPacket(buf, hdrlen+m->data.nicklen+msglen, 3);
}

/* Send an ACK message with the specified message ID. */
static void protoSendACK(uint8_t *msgid, int ack_type) {
    unsigned char buf[256];
    struct Message *m = (struct Message*) buf;

    m->type = MSG_TYPE_ACK;
    m->flags = 0;
    memcpy(m->ack.id,msgid,sizeof(m->ack.id));
    m->ack.ack_type = ack_type;
    protoFillSenderAddress(m->ack.sender);
    sendLoRaPacket(buf, 13); // ACKs have a fixed len of 13 bytes.
}
