/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#ifndef _EINK_H
#define _EINK_H

void setupDisplay();
void setDisplayBacklight();
void displayPrint(const char *str);
void displayImage(const uint8_t *bitmap, int width, int height);

#endif
