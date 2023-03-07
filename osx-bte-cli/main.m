/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#import <Foundation/Foundation.h>
#import "SerialBTE.h"
#include <unistd.h>
#include <string.h>

int main(int argc, const char **argv) {
    const char *namePattern = nil;

    if (argc == 2) {
        if (!strcasecmp(argv[1],"--help")) {
            fprintf(stderr,
"Usage: %s           -- connects to the first ESP32 found\n"
"       %s <pattern> -- connects to device containing <pattern> in name\n",
                argv[0],argv[0]);
            exit(1);
        } else {
            namePattern = argv[1];
        }
    }

    NSString *pattern = nil;
    if (namePattern) pattern = [NSString stringWithCString:namePattern encoding:NSUTF8StringEncoding];

    [[SerialBTE alloc] initWithNamePattern: pattern];
    while(1) {
        /* The program is structured to run in a differnet thread, in case
         * we want to modify it later so that the bluetooth part is
         * handled by Objective-C, and we do our stuff in the C side.
         *
         * However for this simple application it was more practical to do
         * everythign in the Objective-C side, so this is now useless
         * and the main thread will just sleep. */
        sleep(1);
    }
    return 0;
}
