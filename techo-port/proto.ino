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
#include "utils.h"
#include "fci.h"

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

/* This is a dictionary of Neighbor structures (HELLO msg), so
 * it represents the current set of nodes we are sensing. */
struct rax *Neighbors = NULL;

/* Dictionary of Message IDs keys, each pointing to sub-dictionaries of
 * IDs of the nodes that ACKnowledged the message (with such ID). We use this
 * to understand when to suppress multiple transmissions of the same
 * message: if we got ACKs from all the known first-hop nodes, we suppress
 * resending ASAP.
 *
 * Each entry, other than the acknowledging node IDs, has a special entry
 * "ct" storing the creation time, so that we can evict old entries. */
struct rax *WaitingACK = NULL;

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

/* ============================== Prototypss ================================ */

static void protoSendACK(uint8_t *msgid, int ack_type);
static void protoSendHelloMessage(const char *nick, const char *status);


/* =================== Initialization and periodic tasks ==================== */

/* Called by FreakWAN main initialization function. */
void protoInit(void) {
    Neighbors = raxNew();
    WaitingACK = raxNew();
}

/* Called periodically by FreakWAN main loop. */
void protoCron(void) {
    static unsigned long next_hello_time = 0;

    /* Send a periodic HELLO message. */
    if (timeReached(next_hello_time)) {
        fwLog("V:[proto] sending HELLO message");
        next_hello_time = millisPlusRandom(60000,120000);
        protoSendHelloMessage(FW.nick,FW.status);
    }

    /* Remove neighbors we didn't hear HELLO messages for quite some
     * time. */
    struct raxIterator ri;
    raxStart(&ri,Neighbors);
    raxSeek(&ri,"^",NULL,0);
    while(raxNext(&ri)) {
        struct Neighbor *n = (struct Neighbor*) ri.data;
        if (timeElapsedSince(n->last_seen_time) > 60*10*1000) {
            neighborFree(n);
            raxRemove(Neighbors,ri.key,ri.key_len,NULL);
            // Seek again after deletion.
            raxSeek(&ri,">",ri.key,ri.key_len);
            fwLog("V:[proto] Removing timedout neighbor: "
                  "%02x%02x%02x%02x%02x%02x",
                  ri.key[0],ri.key[1],ri.key[2],ri.key[3],ri.key[4],ri.key[5]);
        }
    }
    raxStop(&ri);
}

/* ============================ ACKs collection ============================= */

/* Adds the node ID to the list of nodes that acknowledged the specified
 * message ID.
 *
 * If the ACKs table entry for the specified message does not exist, create
 * a new entry before adding the new node ID.
 *
 * The funciton returns the total amount of ACKs received for the
 * specified message. */
#define ACKS_TABLE_MAX_SIZE 128
#define ACKS_TABLE_ENTRY_TTL 60000 // In milliseconds.
static int waitingACKAddACK(uint8_t *msgid, uint8_t *nodeid) {
    if (raxSize(WaitingACK) >= ACKS_TABLE_MAX_SIZE) return 0;

    struct rax *nodes = (struct rax*) raxFind(WaitingACK,msgid,MSG_ID_LEN);
    if (nodes == raxNotFound) {
        if ((nodes = raxNew()) == NULL) return 0; /* OOM. */
        if (raxInsert(WaitingACK,msgid,MSG_ID_LEN,nodes,NULL) == 0) {
            /* OOM. */
            raxFree(nodes);
            return 0;
        }
        /* Don't handle failure to add the creation time entry here, but
         * instead handle the case it is missing when evicting entries. */
        raxInsert(nodes,(unsigned char*)"ct",2,(void*)millis(),NULL);
    }
    /* Insert the new node that acknowledged the message. For now we
     * don't use the saved ACK time, but saving it costs nothing, since we
     * just cast it to the value pointer in the dictionary. */
    if (raxInsert(nodes,nodeid,SENDER_ID_LEN,(void*)millis(),NULL)) {
        fwLog("D:New ACK for %02x%02x%02x%02x from %02x%02x%02x%02x%02x%02x: "
              "%d ACKs out of %d nodes received.",
            msgid[0],msgid[1],msgid[2],msgid[3],
            nodeid[0],nodeid[1],nodeid[2],nodeid[3],nodeid[4],nodeid[5],
            (int)raxSize(nodes)-1,(int)raxSize(Neighbors));
    }
    return raxSize(nodes)-1; // -1 because of the "ct" extra field.
}

/* ========================== Neighbors handling ============================ */

/* Return the number of known nodes. */
size_t protoGetNeighborsCount(void) {
    return raxSize(Neighbors);
}

/* Free an heap allocated Neighboor structure. */
static void neighborFree(struct Neighbor *n) {
    free(n->nick);
    free(n->status);
    free(n);
}

/* Add a neighbor to our table of sensed nodes (via HELLO messages).
 * If the node was already in the table 0 is returned, otherwise
 * the function returns 1. As a side effect, the table is populated or
 * the existing node is updated. */
#define MAX_NEIGHBORS 128 // Avoid OOM attack.
static int neighborAdd(uint8_t *nodeid, const char *nick, size_t nick_len,
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
        if (raxInsert(Neighbors,nodeid,SENDER_ID_LEN,n,NULL) == 0) {
            /* Out of memory adding item. */
            neighborFree(n);
            return 0;
        }
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

        /* Reply with ACK, if needed. */
        if (!FW.quiet) protoSendACK(m->data.id,m->type);

        int is_media = m->flags & MSG_FLAG_MEDIA;
        int data_len = (int)len-14-m->data.nicklen;
        uint8_t *data = m->data.payload+m->data.nicklen;

        char buf[256+32];
        if (!is_media) {
            snprintf(buf,sizeof(buf),"%.*s> %.*s (rssi: %02.f)",(int)m->data.nicklen,m->data.payload,data_len,data,(double)rssi);
            displayPrint(buf);
            BLEReply(buf);
        } else {
            uint8_t media_type = data[0];
            data++;
            data_len--;
            if (media_type == 0) { /* Image. */
                int w,h;
                uint8_t *bitmap = decode_fci(data,data_len,&w,&h);
                if (!bitmap) {
                    fwLog("[proto] Corrupted FCI image received");
                } else {
                    displayImage(bitmap,w,h);
                    free(bitmap);
                }
            } else {
                fwLog("[proto] Unknown media type %d received",media_type);
            }
        }
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
            fwLog("[proto] New node sensed: %02x%02x%02x%02x%02x%02x",
                m->hello.sender[0], m->hello.sender[1], m->hello.sender[2],
                m->hello.sender[3], m->hello.sender[4], m->hello.sender[5]);
        }
    } else if (m->type == MSG_TYPE_ACK) {
        if (len != 13) return;   // ACKs are fixed length.
        if (waitingACKAddACK(m->ack.id,m->ack.sender) >=
            protoGetNeighborsCount())
        {
            /* Got ACK from all the first-hope nodes? Suppress
             * resending if the packet is still in queue. */
            if (cancelLoRaSend(m->ack.id)) {
                fwLog("[proto] All ACKs for %02x%02x%02x%02x. "
                      "Removed from TX queue.",
                m->ack.id[0],m->ack.id[1],m->ack.id[2],m->ack.id[3]);
            }
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

/* Send a data message with the specified nick, message and flags. */
static void protoSendHelloMessage(const char *nick, const char *status) {
    unsigned char buf[256];
    struct Message *m = (struct Message*) buf;
    int nicklen = strlen(nick);
    const char *msg = status;
    size_t msglen = strlen(status);
    int hdrlen = 10; /* Data header + 1 nick len byte. */

    /* Trim nick and len to never go over max packet size. */
    if (hdrlen+nicklen > sizeof(buf))
        nicklen = sizeof(buf)-hdrlen;
    if (hdrlen+nicklen+msglen > sizeof(buf))
        msglen = sizeof(buf)-hdrlen-nicklen;

    m->type = MSG_TYPE_HELLO;
    m->flags = 0;
    m->hello.seen = protoGetNeighborsCount();
    protoFillSenderAddress(m->hello.sender);
    m->hello.nicklen = nicklen;
    memcpy(m->hello.payload,nick,m->hello.nicklen);
    memcpy(m->hello.payload+m->hello.nicklen,msg,msglen);
    sendLoRaPacket(buf, hdrlen+m->hello.nicklen+msglen, 1);
}
