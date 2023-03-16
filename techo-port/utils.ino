#include <limits.h>

/* Given a time obtained with millis(), the function returns how
 * much milliseconds elapsed since that time. */
unsigned long timeElapsedSince(unsigned long time) {
    unsigned long now = millis();
    if (now > time) return now-time;
    /* Handle wrapping around. */
    return (ULONG_MAX - time) + now;
}
