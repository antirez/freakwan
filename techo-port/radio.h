/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#ifndef _RADIO_H
#define _RADIO_H

void setupLoRa(void);
size_t receiveLoRaPacket(uint8_t *packet, float *rssi);
void sendLoRaPacket(uint8_t *packet, size_t len, int tx_num=1, unsigned long tx_delay=0);
void processLoRaSendQueue(void);
int getLoRaSendQueueLen(void);
void setLoRaParams(void);

#endif
