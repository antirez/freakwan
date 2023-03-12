#pragma once


#include <Arduino.h>

// #define VERSION_1
// #define HIGH_VOLTAGE

#ifndef _PINNUM
#define _PINNUM(port, pin)    ((port)*32 + (pin))
#endif

#if defined(VERSION_1)
#define ePaper_Miso         _PINNUM(1,3)
#else
#define ePaper_Miso         _PINNUM(1,6)
#endif
#define ePaper_Mosi         _PINNUM(0,29)
#define ePaper_Sclk         _PINNUM(0,31)
#define ePaper_Cs           _PINNUM(0,30)
#define ePaper_Dc           _PINNUM(0,28)
#define ePaper_Rst          _PINNUM(0,2)
#define ePaper_Busy         _PINNUM(0,3)
#define ePaper_Backlight    _PINNUM(1,11)

#define LoRa_Miso           _PINNUM(0,23)
#define LoRa_Mosi           _PINNUM(0,22)
#define LoRa_Sclk           _PINNUM(0,19)
#define LoRa_Cs             _PINNUM(0,24)
#define LoRa_Rst            _PINNUM(0,25)
#if defined(VERSION_1)
#define LoRa_Dio0           _PINNUM(1,1)
#else
#define LoRa_Dio0           _PINNUM(0,22)
#endif
#define LoRa_Dio1           _PINNUM(0,20)
#define LoRa_Dio2           //_PINNUM(0,3)
#define LoRa_Dio3           _PINNUM(0,21)
#define LoRa_Dio4           //_PINNUM(0,3)
#define LoRa_Dio5           //_PINNUM(0,3)
#define LoRa_Busy           _PINNUM(0,17)


#define Flash_Cs            _PINNUM(1,15)
#define Flash_Miso          _PINNUM(1,13)
#define Flash_Mosi          _PINNUM(1,12)
#define Flash_Sclk          _PINNUM(1,14)
#define Flash_HOLD          _PINNUM(0,5)
#define Flash_WP            _PINNUM(0,7)


#define Touch_Pin           _PINNUM(0,11)
#define Adc_Pin             _PINNUM(0,4)

#define SDA_Pin             _PINNUM(0,26)
#define SCL_Pin             _PINNUM(0,27)

#define RTC_Int_Pin         _PINNUM(0,16)

#define Gps_Rx_Pin          _PINNUM(1,9)
#define Gps_Tx_Pin          _PINNUM(1,8)

#if defined(VERSION_1)
#define Gps_Wakeup_Pin      _PINNUM(1,2)
#define Gps_pps_Pin         _PINNUM(1,4)
#else
#define Gps_Wakeup_Pin      _PINNUM(1,2)
#define Gps_Reset_Pin       _PINNUM(1,5)
#define Gps_pps_Pin         _PINNUM(1,4)
#endif



#define UserButton_Pin      _PINNUM(1,10)

#if defined(VERSION_1)
#define Power_Enable_Pin    _PINNUM(0,12)
#else
#define Power_Enable_Pin    _PINNUM(0,12)
//#define Power_Enable1_Pin   _PINNUM(0,13)
#endif


#if defined(VERSION_1)
#define GreenLed_Pin        _PINNUM(0,13)
#define RedLed_Pin          _PINNUM(0,14)
#define BlueLed_Pin         _PINNUM(0,15)
#else
#define GreenLed_Pin        _PINNUM(1,1)
#define RedLed_Pin          _PINNUM(1,3)
#define BlueLed_Pin         _PINNUM(0,14)
#endif

#define SerialMon           Serial
#define SerialGPS           Serial2

#define MONITOR_SPEED       115200





