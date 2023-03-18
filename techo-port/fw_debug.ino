/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#include <stdarg.h>

#define DEBUG_BUFFER_SIZE 256

static bool debug = false;

/* Enable / disable debug logs. */
void set_fw_debug(bool state) {
    debug = state;
}

/* Log to the serial, printf() style. */
void fw_debug(const char *format, ...) {
    if (debug == false) return;
    char buffer[DEBUG_BUFFER_SIZE];
    va_list args;
    va_start(args, format);
    int len = vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    if (len > 0 && buffer[len-1] == '\n' && len < sizeof(buffer)-1) {
        buffer[len-1] = '\r';
        buffer[len] = '\n';
        buffer[len+1] = 0;
    }
    Serial.print(buffer);
}
