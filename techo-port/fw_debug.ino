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
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    Serial.print(buffer);
}
