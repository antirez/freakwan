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
};

extern struct FreakWANGlobalSettings FW;
