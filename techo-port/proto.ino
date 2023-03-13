#include <stdint.h>
#include "eink.h"

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
            uint8_t payload[1]; // Nick + text.
        } data;
    };
};

void protoProcessPacket(const unsigned char *packet, size_t len, float rssi) {
    struct msg *m = (struct msg*) packet;
    if (len < 2) return;    // No room for commmon header.

    /* Process data packet. */
    if (m->type == 0) {
        if (len < 14) return;   // No room for data header.
        char buf[256+32];
        snprintf(buf,sizeof(buf),"%.*s> %.*s (rssi: %02.f)",(int)m->data.nicklen,m->data.payload,(int)len-14-m->data.nicklen,m->data.payload+m->data.nicklen,(double)rssi);
        displayPrint(buf);
    }
}
