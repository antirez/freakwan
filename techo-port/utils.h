/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#ifndef _UTILS_H
#define _UTILS_H

unsigned long timeElapsedSince(unsigned long time);
int timeReached(unsigned long time);
unsigned long millisPlusRandom(unsigned long minrand, unsigned long maxrand);
unsigned long millisPlus(unsigned long ms);

#endif
