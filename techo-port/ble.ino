/*********************************************************************
 This is an example for our nRF52 based Bluefruit LE modules

 Pick one up today in the adafruit shop!

 Adafruit invests time and resources providing this open source code,
 please support Adafruit and open-source hardware by purchasing
 products from Adafruit!

 MIT license, check LICENSE for more information
 All text above, and the splash screen below must be included in
 any redistribution
*********************************************************************/
#include <bluefruit.h>

// BLE Service
BLEDfu  bledfu;  // OTA DFU service
BLEDis  bledis;  // device information
BLEUart bleuart; // uart over ble
BLEBas  blebas;  // battery
bool BLEConnected = false;

void setupBLE(void) {
  Bluefruit.autoConnLed(true);
  Bluefruit.configPrphBandwidth(BANDWIDTH_MAX);

  Bluefruit.begin();
  Bluefruit.setTxPower(4);    // Check bluefruit.h for supported values
  //Bluefruit.setName(getMcuUniqueID()); // useful testing with multiple central connections
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

void BLEProcessCommands(void) {
    if (BLEConnected == false) return;
    // Forward from BLEUART to HW Serial
    while (bleuart.available()) {
        uint8_t buf[256];
        int len = bleuart.read(buf,sizeof(buf));
        if (len) {
            Serial.write(buf,len);
            bleuart.write("hey!",4);
        }
    }
}

void connect_callback(uint16_t conn_handle) {
    BLEConnected = true;
    BLEConnection* connection = Bluefruit.Connection(conn_handle);
    char central_name[32] = { 0 };
    connection->getPeerName(central_name, sizeof(central_name));
    Serial.print("Connected to ");
    Serial.println(central_name);
}

void disconnect_callback(uint16_t conn_handle, uint8_t reason) {
    (void) conn_handle;
    (void) reason;

    BLEConnected = false;
    Serial.println();
    Serial.print("Disconnected, reason = 0x");
    Serial.println(reason, HEX);
}
