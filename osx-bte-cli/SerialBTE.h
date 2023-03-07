/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#import <Foundation/Foundation.h>
#import <CoreBluetooth/CoreBluetooth.h>
#include <stdio.h>

@interface SerialBTE: NSObject
<CBCentralManagerDelegate, CBPeripheralDelegate>
{
    bool shouldScan;
    CBPeripheral *peripheral;   // Connected device
    CBUUID *serviceUuid;        // UUID we scan for.
    dispatch_queue_t btequeue;  // Queue used by the Central Manager
    CBCharacteristic *readChar, *writeChar; // Serial BTE write and read chars.
}

@property (retain) NSMutableArray *discoveredDevices;
@property (strong, nonatomic) CBCentralManager *manager;

- (instancetype)init;
- (void)startScan;
@end
