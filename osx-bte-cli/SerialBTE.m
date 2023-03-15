/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#import "SerialBTE.h"
#include <stdio.h>
#include <unistd.h>

@implementation SerialBTE
@synthesize discoveredDevices;

- (instancetype)init
{
    return [self initWithNamePattern: nil];
}

- (instancetype)initWithNamePattern:(NSString *) pattern
{
    self = [super init];
    if (self) {
        self.discoveredDevices = [NSMutableArray array];
        serviceUuid = [CBUUID UUIDWithString: @"6E400001-B5A3-F393-E0A9-E50E24DCCA9E"];
        readChar = nil;
        writeChar = nil;
        peripheral = nil;
        namepat = pattern;
        btequeue = dispatch_queue_create("centralmanager", DISPATCH_QUEUE_SERIAL);
        _manager = [[CBCentralManager alloc] initWithDelegate: self
                                                        queue: btequeue];
    }
    [self performSelectorInBackground:@selector(CBThread:)
                           withObject:nil];
    return self;
}

- (void) CBThread:(id)arg {
    NSRunLoop *runLoop = [NSRunLoop currentRunLoop];
    int tick = 0;
    while(1) {
        NSDate *endDate = [[NSDate alloc] initWithTimeIntervalSinceNow:0.1];
        [runLoop runUntilDate:endDate];

        if (peripheral != nil && writeChar != nil) {
            printf("> "); fflush(stdout);
            char buf[256];
            if (fgets(buf,sizeof(buf),stdin) != NULL) {
                size_t l = strlen(buf);
                if (l > 1 && buf[l-1] == '\n') buf[l-1] = 0;
                NSString *stringValue = [NSString stringWithCString:buf encoding:NSUTF8StringEncoding];
                NSData *dataValue = [stringValue dataUsingEncoding:NSUTF8StringEncoding];
                [peripheral writeValue:dataValue forCharacteristic:writeChar type:CBCharacteristicWriteWithResponse];
                [dataValue release];
            } else {
                exit(0);
            }
        }
        usleep(100000);
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
        printf("Found: %s (%s): ", deviceName, localName ? localName : "?");
        if (namepat != nil) {
            const char *pat = [namepat cStringUsingEncoding:NSASCIIStringEncoding];
            if (strcasestr(deviceName,pat) == NULL &&
                strcasestr(localName,pat) == NULL)
            {
                printf("Discarding (name mismatch)\n");
                return;
            }
        }
        printf("Connecting...\n");
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
    printf("Connected.\n");
    [aPeripheral setDelegate:self];
    [aPeripheral discoverServices:nil];
}

/* Called if on disconnection from the currently connected device. */
- (void) centralManager: (CBCentralManager *)central
didDisconnectPeripheral: (CBPeripheral *)aPeripheral
                  error: (NSError *)error
{
    fprintf(stderr,"\nDevice disconnected. Exiting...\n");
    exit(1);
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
        NSLog(@"Service: %@", aService.UUID);
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
            printf("Notify characteristic found.\n");
            [aPeripheral setNotifyValue:YES forCharacteristic:aChar];
            [aPeripheral readValueForCharacteristic:aChar];
            readChar = aChar;
            [readChar retain];
            NSLog(@"Notify Char: %@ about service %@", readChar.UUID, service.UUID);
        } else if (aChar.properties & CBCharacteristicPropertyWrite) {
            writeChar = aChar;
            [writeChar retain];
            printf("Write characteristic found.\n");
            NSLog(@"Write Char: %@ about service %@", writeChar.UUID, service.UUID);
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
        printf("%.*s\n", (int)l, p);
    }
}

- (void)peripheral: (CBPeripheral *)peripheral didModifyServices:(NSArray<CBService *> *)invalidatedServices
{
    printf("[didModifyServices] called\n");
    exit(1);
}

@end
