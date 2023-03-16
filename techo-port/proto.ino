/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#include <stdint.h>
#include "proto.h"
#include "eink.h"
#include "radio.h"

struct msg {
    /* Common header */
    uint8_t type;       // Packet type.
    uint8_t flags;      // Packet flags.
    
    /* Type specifid header. */
    union {
        struct {
            uint8_t id[4];  // Message ID.
            uint8_t ttl;    // Time to live.
            uint8_t sender[6];  // Sender address.
            uint8_t nicklen;    // Nick length.
            uint8_t payload[0]; // Nick + text.
        } data;
    };
};

void protoProcessPacket(const unsigned char *packet, size_t len, float rssi) {
    struct msg *m = (struct msg*) packet;
    if (len < 2) return;    // No room for commmon header.

    /* Process data packet. */
    if (m->type == MSG_TYPE_DATA) {
        if (len < 14) return;   // No room for data header.
        char buf[256+32];
        snprintf(buf,sizeof(buf),"%.*s> %.*s (rssi: %02.f)",(int)m->data.nicklen,m->data.payload,(int)len-14-m->data.nicklen,m->data.payload+m->data.nicklen,(double)rssi);
        displayPrint(buf);
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
    sendLoRaPacket(buf, hdrlen+m->data.nicklen+msglen);
}
