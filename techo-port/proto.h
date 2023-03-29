/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#ifndef _PROTO_H
#define _PROTO_H

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

void protoProcessPacket(const unsigned char *packet, size_t len, float rssi);
void protoSendDataMessage(const char *nick, const char *msg, size_t msglen, uint8_t flags);
void protoSendACK(uint8_t *msgid, int ack_type);

#endif
