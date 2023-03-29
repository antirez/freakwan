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

struct msg {
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
    };
};

/* Given the message ID, return the index in the message cache table. */
unsigned int MessageCacheHash(uint8_t *mid) {
    return (mid[0]<<1) ^ (mid[1]<<1) ^ mid[2] ^ mid[3];
}

/* Add the message ID into the message cache. */
void MessageCacheAdd(uint8_t *mid) {
    unsigned int offset = MessageCacheHash(mid)*MSG_ID_LEN;
    memcpy(MessageCache+offset,mid,MSG_ID_LEN);
}

/* Look for the message ID in the message cache. Returns 1 if the ID
 * is found, otherwise 0. */
int MessageCacheFind(uint8_t *mid) {
    unsigned int offset = MessageCacheHash(mid)*MSG_ID_LEN;
    return memcmp(MessageCache+offset,mid,MSG_ID_LEN) == 0;
}

void protoProcessPacket(const unsigned char *packet, size_t len, float rssi) {
    struct msg *m = (struct msg*) packet;
    if (len < 2) return;    // No room for commmon header.

    /* Process data packet. */
    if (m->type == MSG_TYPE_DATA) {
        if (len < 14) return;   // No room for data header.

        /* Was the message already processed? */
        if (MessageCacheFind(m->data.id)) return;
        MessageCacheAdd(m->data.id);

        char buf[256+32];
        snprintf(buf,sizeof(buf),"%.*s> %.*s (rssi: %02.f)",(int)m->data.nicklen,m->data.payload,(int)len-14-m->data.nicklen,m->data.payload+m->data.nicklen,(double)rssi);
        displayPrint(buf);
        BLEReply(buf);
    }
}

/* Write six bytes of the device ID to the target string. */
void protoFillSenderAddress(uint8_t *sender) {
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
    struct msg *m = (struct msg*) buf;
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
