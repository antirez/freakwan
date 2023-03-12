#include <RadioLib.h>
#include "proto.h"

SX1262          radio     = nullptr;        // LoRa radio object

void LoRaPacketReceived(void)
{
    unsigned char packet[256];
    size_t len = radio.getPacketLength();
    int state = radio.readData(packet,len);
    protoProcessPacket(packet,len);

    // Put the chip back in receive mode.
    radio.startReceive();
}

void setupLoRa(void) {
    SPIClass *rfPort = new SPIClass(
        /*SPIPORT*/NRF_SPIM3,
        /*MISO*/ LoRa_Miso,
        /*SCLK*/LoRa_Sclk,
        /*MOSI*/LoRa_Mosi);
    rfPort->begin();

    SPISettings spiSettings;

    radio = new Module(LoRa_Cs, LoRa_Dio1, LoRa_Rst, LoRa_Busy, *rfPort, spiSettings);

    SerialMon.print("[SX1262] Initializing ...  ");
    int state = radio.begin(869.5);
    if (state != RADIOLIB_ERR_NONE) {
        SerialMon.print("[SX1262] Initialization failed: ");
        SerialMon.println(state);
    } else {
        SerialMon.println("[SX1262] Initialization succeeded.");
        radio.setOutputPower(10);
        radio.setSyncWord(0x12);
        radio.setBandwidth(250.0);
        radio.setSpreadingFactor(12);
        radio.setCodingRate(8);
        radio.setPreambleLength(12);
        radio.setCRC(true);
        radio.setRxBoostedGainMode(RADIOLIB_SX126X_RX_GAIN_BOOSTED,true);
        //radio.setTCXO(2.4);
        
        radio.setCurrentLimit(80);
        radio.setDio1Action(LoRaPacketReceived);
        radio.standby();
        radio.startReceive();
    }
}
