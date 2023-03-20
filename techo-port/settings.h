/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#ifndef _SETTINGS_H
#define _SETTINGS_H

/* Global configuration shared application-wide. This structure
 * should only contain configurable parameters, and not references to
 * objects representing harware or other stuff, that should instead be
 * global vars inside each file handling each specific aspect. */

struct FreakWANGlobalSettings {
    char nick[16];              /* Chat nickname / ID. */
    double lora_freq;           /* LoRa center frequency. */
    int lora_sp;                /* LoRa spreading. */
    int lora_cr;                /* LoRa coding rate. */
    int lora_bw;                /* LoRa bandwidth. */
    int lora_tx_power;          /* LoRa TX power in dbm. */
    bool automsg;               /* Send periodic automatic messages. */
};

extern struct FreakWANGlobalSettings FW;

#endif
