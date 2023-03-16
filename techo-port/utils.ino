/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#include <limits.h>

/* Given a time obtained with millis(), the function returns how
 * much milliseconds elapsed since that time. */
unsigned long timeElapsedSince(unsigned long time) {
    unsigned long now = millis();
    if (now > time) return now-time;
    /* Handle wrapping around. */
    return (ULONG_MAX - time) + now;
}
