/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#include <bluefruit.h>
#include "settings.h"

// BLE Service
BLEDfu  bledfu;  // OTA DFU service
BLEDis  bledis;  // device information
BLEUart bleuart; // uart over ble
BLEBas  blebas;  // battery
bool BLEConnected = false;

void setupBLE(void) {
  Bluefruit.autoConnLed(false); // Don't use the led to show BLE connection.
  Bluefruit.configPrphBandwidth(BANDWIDTH_MAX);

  Bluefruit.begin();
  Bluefruit.setTxPower(4);
  char btname[16];
  snprintf(btname,sizeof(btname),"FW_%s",FW.nick);
  Bluefruit.setName(btname);
  Bluefruit.Periph.setConnectCallback(connect_callback);
  Bluefruit.Periph.setDisconnectCallback(disconnect_callback);

  // Start OTA DFU serivce.
  bledfu.begin();

  // Configure and Start Device Information Service
  bledis.setManufacturer("LILYGO");
  bledis.setModel("T-ECHO");
  bledis.begin();

  // Configure and Start BLE Uart Service
  bleuart.begin();

  // Start BLE Battery Service
  blebas.begin();
  blebas.write(100); // XXX: We should write current battery level here.

  // Set up and start advertising
  startAdv();
}

void startAdv(void) {
  // Advertising packet
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(bleuart);

  // No room in the main packet. Set the local name in the response packet.
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);   // In unit of 0.625 ms.
  Bluefruit.Advertising.setFastTimeout(30);     // Timeout in seconds.
  Bluefruit.Advertising.start(0);               // Never stop advertising.
}

/* Reply callback to pass to the CLI handling code, so that we can
 * see CLI command replies in the BLE shell. */
void BLEReplyCallback(const char *msg) {
    if (BLEConnected == false) return;
    bleuart.write(msg,strlen(msg));
}

void BLEProcessCommands(void) {
    if (BLEConnected == false) return;
    // Forward from BLEUART to HW Serial
    while (bleuart.available()) {
        uint8_t buf[256];
        int len = bleuart.read(buf,sizeof(buf)-1);
        if (len) {
            /* Null term and strip final newlines if any. */
            buf[len] = 0;
            while(len && (buf[len-1] == '\r' || buf[len-1] == '\n'))
                buf[--len] = 0;
            if (len) {
                cliHandleCommand((const char*)buf,BLEReplyCallback);
                Serial.write(buf,len);
            }
        }
    }
}

void connect_callback(uint16_t conn_handle) {
    BLEConnected = true;
    BLEConnection *connection = Bluefruit.Connection(conn_handle);
    char central_name[32] = { 0 };
    connection->getPeerName(central_name, sizeof(central_name));
    Serial.print("Connected to ");
    Serial.println(central_name);
}

void disconnect_callback(uint16_t conn_handle, uint8_t reason) {
    (void) conn_handle;
    BLEConnected = false;
    Serial.print("Disconnected, reason = 0x");
    Serial.println(reason, HEX);
}
