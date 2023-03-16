#ifndef _RADIO_H
#define _RADIO_H

void setupLoRa(void);
size_t receiveLoRaPacket(uint8_t *packet, float *rssi);
void sendLoRaPacket(uint8_t *packet, size_t len);
void processLoRaSendQueue(void);

#endif
