/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#ifndef _PROTO_H
#define _PROTO_H

void protoInit(void);
void protoCron(void);
void protoProcessPacket(const unsigned char *packet, size_t len, float rssi);
void protoSendDataMessage(const char *nick, const char *msg, size_t msglen, uint8_t flags);
size_t protoGetNeighborsCount(void);

#endif
