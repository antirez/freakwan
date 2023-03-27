/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#include <stdio.h>
#include <unistd.h>
#import "SerialBTE.h"
#include "linenoise.h"

struct linenoiseState LineNoiseState;
char LineNoiseBuffer[1024];

@implementation SerialBTE
@synthesize discoveredDevices;

- (instancetype)init
{
    return [self initWithNamePattern: nil];
}

- (instancetype)initWithNamePattern:(NSString *) pattern
{
    linenoiseEditStart(&LineNoiseState,-1,-1,LineNoiseBuffer,sizeof(LineNoiseBuffer),"serial> ");
    self = [super init];
    if (self) {
        self.discoveredDevices = [NSMutableArray array];
        serviceUuid = [CBUUID UUIDWithString: @"6E400001-B5A3-F393-E0A9-E50E24DCCA9E"];
        readChar = nil;
        writeChar = nil;
        peripheral = nil;
        namepat = pattern;
        btequeue = dispatch_get_main_queue();
        _manager = [[CBCentralManager alloc] initWithDelegate: self
                                                        queue: btequeue];
    }

    /* Register a callback() for when there is data in the standard input,
     * that is, the user typed something. */
    int fileDescriptor = fileno(stdin);
    dispatch_source_t stdinSource =
	    dispatch_source_create(DISPATCH_SOURCE_TYPE_READ,
	    fileDescriptor, 0, dispatch_get_main_queue());
    dispatch_source_set_event_handler(stdinSource, ^{
        char *line = linenoiseEditFeed(&LineNoiseState);
        if (line == linenoiseEditMore) return;
        linenoiseEditStop(&LineNoiseState);
        if (line == NULL) exit(0);
        linenoiseHistoryAdd(line); /* Add to the history. */

        /* Write what the user typed to the device BLE serial. */
        if (peripheral != nil && writeChar != nil) {
            size_t l = strlen(line);
            if (l > 1 && line[l-1] == '\n') line[l-1] = 0;
            NSString *stringValue = [NSString stringWithCString:line encoding:NSUTF8StringEncoding];
            NSData *dataValue = [stringValue dataUsingEncoding:NSUTF8StringEncoding];
            [peripheral writeValue:dataValue forCharacteristic:writeChar type:CBCharacteristicWriteWithResponse];
        }

        /* Reset line editing state. */
        linenoiseFree(line);
        linenoiseEditStart(&LineNoiseState,-1,-1,LineNoiseBuffer,sizeof(LineNoiseBuffer),"serial> ");

    });
    dispatch_resume(stdinSource);

    return self;
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
    if ([manager state] == CBManagerStatePoweredOn) {
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
    NSString *localNameValue = [advertisementData valueForKey:@"kCBAdvDataLocalName"];
    const char *localName = localNameValue != nil ? [localNameValue cStringUsingEncoding:NSASCIIStringEncoding] : NULL;

    if (deviceName) {
        linenoiseHide(&LineNoiseState);
        printf("Found: %s (%s): ", deviceName, localName ? localName : "?");
        linenoiseShow(&LineNoiseState);
        if (namepat != nil) {
            const char *pat = [namepat cStringUsingEncoding:NSASCIIStringEncoding];
            if (strcasestr(deviceName,pat) == NULL &&
                (localName == NULL || strcasestr(localName,pat) == NULL))
            {
                linenoiseHide(&LineNoiseState);
                printf("Discarding (name mismatch)\n");
                linenoiseShow(&LineNoiseState);
                return;
            }
        }
        linenoiseHide(&LineNoiseState);
        printf("Connecting...\n");
        linenoiseShow(&LineNoiseState);
    } else {
        return;
    }
    
    /* Conencting will fail if we don't create a durable
     * reference to the peripheral, so we add it into the array. */
    [peripherals addObject:aPeripheral];
    [self connectToPeripheral: aPeripheral];
}

/* Called as a result of connectToPeripheral, once the connection
 * is finalized. */
- (void) centralManager: (CBCentralManager *)central
   didConnectPeripheral: (CBPeripheral *)aPeripheral
{
    linenoiseHide(&LineNoiseState);
    printf("Connected.\n");
    linenoiseShow(&LineNoiseState);
    [aPeripheral setDelegate:self];
    [aPeripheral discoverServices:nil];
}

/* Called if on disconnection from the currently connected device. */
- (void) centralManager: (CBCentralManager *)central
didDisconnectPeripheral: (CBPeripheral *)aPeripheral
                  error: (NSError *)error
{
    fprintf(stderr,"\r\nDevice disconnected. Exiting...\r\n");
    exit(1);
}

/* Called on connection error. */
- (void) centralManager: (CBCentralManager *)central didFailToConnectPeripheral:(CBPeripheral *)aPeripheral error:(NSError *)error
{
    linenoiseHide(&LineNoiseState);
    linenoiseHide(&LineNoiseState);
    NSLog(@"Fail to connect to peripheral: %@ with error = %@", aPeripheral, [error localizedDescription]);
    linenoiseShow(&LineNoiseState);
    linenoiseShow(&LineNoiseState);
}

/* Start scanning. */
- (void) startScan
{
    linenoiseHide(&LineNoiseState);
    printf("Start scanning\n");
    linenoiseShow(&LineNoiseState);
    
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
    // printf("Stop scannign and connecting\n");
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
    for (CBService *aService in aPeripheral.services)
    {
        linenoiseHide(&LineNoiseState);
        NSLog(@"Service: %@", aService.UUID);
        linenoiseShow(&LineNoiseState);
        if ([aService.UUID isEqual:serviceUuid]) {
            [aPeripheral discoverCharacteristics:nil forService:aService];
        }
    }
}

/* Called upon completion of discoverCharacteristics, with an array of
 * characteristics provided by a given service of the device. */
- (void) peripheral: (CBPeripheral *)aPeripheral didDiscoverCharacteristicsForService:(CBService *)service error:(NSError *)error
{
    for (CBCharacteristic *aChar in service.characteristics)
    {
        // NSLog(@"Service: %@ with Char: %@", [aChar service].UUID, aChar.UUID);
        if (aChar.properties & CBCharacteristicPropertyNotify)
        {
            linenoiseHide(&LineNoiseState);
            printf("Notify characteristic found.\r\n");
            [aPeripheral setNotifyValue:YES forCharacteristic:aChar];
            [aPeripheral readValueForCharacteristic:aChar];
            readChar = aChar;
            [readChar retain];
            NSLog(@"Notify Char: %@ about service %@", readChar.UUID, service.UUID);
            linenoiseShow(&LineNoiseState);
        } else if (aChar.properties & CBCharacteristicPropertyWrite) {
            writeChar = aChar;
            [writeChar retain];
            linenoiseHide(&LineNoiseState);
            printf("Write characteristic found.\r\n");
            NSLog(@"Write Char: %@ about service %@", writeChar.UUID, service.UUID);
            linenoiseShow(&LineNoiseState);
        }
    }
}

/* Callback of reads, after readValueForCharacteristic. */
- (void) peripheral: (CBPeripheral *)aPeripheral didUpdateValueForCharacteristic:(CBCharacteristic *)characteristic error:(NSError *)error
{
    NSData *newval = characteristic.value;

    if (newval) {
        size_t l = [newval length];
        char *p = (char*)newval.bytes;
        while (l && p[l-1] == '\n') l--;
        linenoiseHide(&LineNoiseState);
        printf("%.*s\r\n", (int)l, p);
        linenoiseShow(&LineNoiseState);
    }
}

- (void)peripheral: (CBPeripheral *)peripheral didModifyServices:(NSArray<CBService *> *)invalidatedServices
{
    printf("[didModifyServices] called\r\n");
    exit(1);
}

@end
