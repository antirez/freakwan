/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#import <Foundation/Foundation.h>
#import "SerialBTE.h"
#include <unistd.h>

int main(int argc, const char **argv) {
    [SerialBTE new];
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
