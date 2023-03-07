/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#import "SerialBTE.h"
#include <unistd.h>

@implementation SerialBTE
@synthesize discoveredDevices;

- (instancetype)init
{
    self = [super init];
    if (self) {
        self.discoveredDevices = [NSMutableArray array];
        shouldScan = true;
        serviceUuid = [CBUUID UUIDWithString: @"6E400001-B5A3-F393-E0A9-E50E24DCCA9E"];
        readChar = nil;
        writeChar = nil;
        peripheral = nil;
        btequeue = dispatch_queue_create("centralmanager", DISPATCH_QUEUE_SERIAL);
        _manager = [[CBCentralManager alloc] initWithDelegate: self
                                                        queue: btequeue];
    }
    [self performSelectorInBackground:@selector(CBThread:)
                           withObject:nil];
    return self;
}

- (void) CBThread:(id)arg {
    printf("--- In CBThread ---\n");
    NSRunLoop *runLoop = [NSRunLoop currentRunLoop];
    int tick = 0;
    while(1) {
        NSDate *endDate = [[NSDate alloc] initWithTimeIntervalSinceNow:0.1];
        [runLoop runUntilDate:endDate];
        usleep(100000);

        tick++;
        if (tick % 20 == 0 && peripheral != nil && writeChar != nil) {
            printf("WRITE LS\n");
            NSString *stringValue = @"!ls";
            NSData *dataValue = [stringValue dataUsingEncoding:NSUTF8StringEncoding];
            [peripheral writeValue:dataValue forCharacteristic:writeChar type:CBCharacteristicWriteWithResponse];
        }

    }
}

- (void)dealloc
{
    [_manager stopScan];
    [_manager dealloc];
    [super dealloc];
}

/* This is called when our Central Manager is ready. So this is the
 * entry point of the program in some way. Here we will start
 * a BTE scanning or other operations. */
- (void)centralManagerDidUpdateState:(CBCentralManager *)manager
{
    printf("centralManagerDidUpdateState called\n");
    if ([manager state] == CBManagerStatePoweredOn && shouldScan)
    {
        [self startScan];
    }
}

/* Called each time the Central Manager discovers a peripheral
 * while scanning. */
- (void)centralManager:(CBCentralManager *)central
 didDiscoverPeripheral:(CBPeripheral *)aPeripheral
     advertisementData:(NSDictionary *)advertisementData
                  RSSI:(NSNumber *)RSSI
{
    NSMutableArray *peripherals =  [self mutableArrayValueForKey:@"discoveredDevices"];
    const char *deviceName = [[aPeripheral name] cStringUsingEncoding:NSASCIIStringEncoding];
    if (deviceName)
        printf("Found: %s\n", deviceName);
    
    if ([[aPeripheral name] isEqualToString: @"ESP32"])
    {
        /* Conencting will fail if we don't create a durable
         * reference to the peripheral, so we add it into the array. */
        [peripherals addObject:aPeripheral];
        [self connectToPeripheral: aPeripheral];
    }
}

/* Called as a result of connectToPeripheral, once the connection
 * is finalized. */
- (void) centralManager: (CBCentralManager *)central
   didConnectPeripheral: (CBPeripheral *)aPeripheral
{
    printf("Connected.\n");
    [aPeripheral setDelegate:self];
    printf("Discover services of peripheral...\n");
    [aPeripheral discoverServices:nil];
}

/* Called if on disconnection from the currently connected device. */
- (void) centralManager: (CBCentralManager *)central
didDisconnectPeripheral: (CBPeripheral *)aPeripheral
                  error: (NSError *)error
{
    printf("didDisconnectPeripheral\n");
}

/* Called on connection error. */
- (void) centralManager: (CBCentralManager *)central didFailToConnectPeripheral:(CBPeripheral *)aPeripheral error:(NSError *)error
{
    NSLog(@"Fail to connect to peripheral: %@ with error = %@", aPeripheral, [error localizedDescription]);
}

/* Start scanning. */
- (void) startScan
{
    printf("Start scanning\n");
    
    if (!serviceUuid)
    {
        [_manager scanForPeripheralsWithServices: nil options: nil];
    }
    else
    {
        [_manager scanForPeripheralsWithServices: [NSArray arrayWithObject: serviceUuid] options: nil];
    }
}

/* Connect to the specified device. */
- (void) connectToPeripheral: (CBPeripheral *)aPeripheral
{
    printf("Stop scannign and connecting\n");
    [_manager stopScan];
    peripheral = aPeripheral;
    NSDictionary *connectOptions = @{
        CBConnectPeripheralOptionNotifyOnConnectionKey: @YES,
        CBConnectPeripheralOptionNotifyOnDisconnectionKey: @YES,
        CBConnectPeripheralOptionNotifyOnNotificationKey: @YES,
        CBConnectPeripheralOptionStartDelayKey: @0
    };
    [_manager connectPeripheral:peripheral options:connectOptions];
}

/* Called on completion of discoverServices call, will report the
 * discovered services provided by the device. */
- (void) peripheral: (CBPeripheral *)aPeripheral
didDiscoverServices:(NSError *)error
{
    printf("In discover services callback:\n");
    for (CBService *aService in aPeripheral.services)
    {
        NSLog(@"Service found with UUID: %@", aService.UUID);
        [aPeripheral discoverCharacteristics:nil forService:aService];
    }
}

/* Called upon completion of discoverCharacteristics, with an array of
 * characteristics provided by a given service of the device. */
- (void) peripheral: (CBPeripheral *)aPeripheral didDiscoverCharacteristicsForService:(CBService *)service error:(NSError *)error
{
    printf("Characteristic discovered:\n");
    for (CBCharacteristic *aChar in service.characteristics)
    {
        NSLog(@"Service: %@ with Char: %@", [aChar service].UUID, aChar.UUID);
        if (aChar.properties & CBCharacteristicPropertyNotify)
        {
            printf("IS NOTIFY\n");
            [aPeripheral setNotifyValue:YES forCharacteristic:aChar];
            [aPeripheral readValueForCharacteristic:aChar];
            readChar = aChar;
            [readChar retain];
        } else if (aChar.properties & CBCharacteristicPropertyWrite) {
            writeChar = aChar;
            [writeChar retain];
            printf("WRITING\n");
            NSString *stringValue = @"!nick";
            NSData *dataValue = [stringValue dataUsingEncoding:NSUTF8StringEncoding];
            [aPeripheral writeValue:dataValue forCharacteristic:aChar type:CBCharacteristicWriteWithResponse];
        }
    }
}

/* Callback of reads, after readValueForCharacteristic. */
- (void) peripheral: (CBPeripheral *)aPeripheral didUpdateValueForCharacteristic:(CBCharacteristic *)characteristic error:(NSError *)error
{
    NSData *newval = characteristic.value;
    if (newval) printf("%s",(char*)newval.bytes);
}

- (void)peripheral: (CBPeripheral *)peripheral didModifyServices:(NSArray<CBService *> *)invalidatedServices
{
    printf("[didModifyServices] called\n");
    exit(1);
}

@end
