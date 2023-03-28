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

/* Return true (1) if the specified time was already reached.
 * Because of wrap around, we have to use some heuritic, because there
 * are two possibilities. First: the current time is smaller than the
 * time given as argument (the time to reach):
 *
 * |---------------------------------------------|
 *    \_ current time        \_ given time
 *
 * In this case, either the given time was not yet reached, or the
 * current time wrapped around. If the given time is farest in the
 * future than half of the whole time scale, we consider it reached and
 * assume a wrap around happened.
 *
 * Now consider the other case:
 *
 * |---------------------------------------------|
 *    \_ given time        \_ current time
 *
 * In this case the time may either be already reached
 * or the given time wrapper around when setting it to
 * the future. We apply the same rule: if the time looks
 * expired for more than half of the whole time scale, we
 * assume that a wrap around happened, and the timer is yet
 * not reached.
 */
int timeReached(unsigned long time) {
    unsigned long now = millis();
    unsigned long delta;

    if (time > now) {
        delta = time-now;
        return delta > ULONG_MAX/2;
    } else {
        delta = now-time;
        return delta < ULONG_MAX/2;
    }
}

/* Return the current time plus a random amount of milliseconds from
 * minrand to maxrand. */
unsigned long millisPlusRandom(unsigned long minrand, unsigned long maxrand) {
    unsigned long delta = maxrand-minrand;
    unsigned long plus = rand() % (delta+1);
    return millis() + plus;
}
