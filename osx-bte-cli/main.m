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
    CFRunLoopRun();
    return 0;
}
