#include <TinyGPS++.h>
#include "hwconfig.h"
#include "log.h"

TinyGPSPlus *GPS;

void setupGPS(void) {
    SerialGPS.setPins(Gps_Rx_Pin, Gps_Tx_Pin);
    SerialGPS.begin(9600);
    SerialGPS.flush();
    pinMode(Gps_pps_Pin, INPUT);
    pinMode(Gps_Wakeup_Pin, OUTPUT);

    /* Power on the GPS by raising the wakeup pin high. */
    digitalWrite(Gps_Wakeup_Pin, HIGH);
    delay(10);


    /* Reset the GPS putting the reset pin low for 10 milliseconds. */
    pinMode(Gps_Reset_Pin, OUTPUT);
    digitalWrite(Gps_Reset_Pin, HIGH);
    delay(10);
    digitalWrite(Gps_Reset_Pin, LOW);
    delay(10);
    digitalWrite(Gps_Reset_Pin, HIGH);

    GPS = new TinyGPSPlus();
}

/* This is called periodically to read data from the GPS. */
void GPSCron(void) {
    while (SerialGPS.available() > 0) {
        GPS->encode(SerialGPS.read());
    }

    if (GPS->location.isUpdated()) {
        fwLog("GPS %f,%f", GPS->location.lat(),
                           GPS->location.lng());
    }
}
