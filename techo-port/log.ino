/* Copyright (C) 2023 Salvatore Sanfilippo <antirez@gmail.com>
 * All Rights Reserved
 *
 * This code is released under the BSD 2 clause license.
 * See the LICENSE file for more information. */

#include <stdarg.h>

static int LogLevel = 3; // Info

/* Set log level. Return false if the log level given is not valid.  */
bool fwSetLogLevel(const char *level) {
    if (!strcasecmp(level,"warning")) LogLevel = 4;
    else if (!strcasecmp(level,"info")) LogLevel = 3;
    else if (!strcasecmp(level,"verbose")) LogLevel = 2;
    else if (!strcasecmp(level,"debug")) LogLevel = 1;
    else if (!strcasecmp(level,"tracing")) LogLevel = 0;
    else return false;
    return true;
}

/* Log to the serial, printf() style. There are different log levels
 * that the caller can select by prefixing the log line with the
 * following initial two characters:
 *
 * "W:" Warning     (level 4) Critical information logged at any level.
 * "I:" Info        (level 3) Useful information about system status.
 * "V:" Verbose.    (level 2) Additional info normally not useful.
 * "D:" Debug.      (level 1) Debugging information, not at high rate.
 * "T:" Tracing.    (level 0) Step by step debugging information.
 *
 * Lines without any log level indication goes to "info". Depending on
 * the log level set (using setLoglevel()), the system will log all
 * the messages at the selected level and at higher levels. */
void fwLog(const char *format, ...) {
    /* Select log level, depending on the first two characters. */
    int loglevel = 3;
    if (format[0] && format[1] == ':') {
        switch(format[0]) {
        case 'W': loglevel = 4; break;
        case 'I': loglevel = 3; break;
        case 'V': loglevel = 2; break;
        case 'D': loglevel = 1; break;
        case 'T': loglevel = 0; break;
        }
        format += 2;
    }

    /* Return ASAP if current loglevel settings discard this message. */
    if (loglevel < LogLevel) return;

    /* Log the line. We limit to a maximum buffer for simplicity. */
    char buffer[256];
    va_list args;
    va_start(args, format);
    int len = vsnprintf(buffer, sizeof(buffer)-2, format, args);
    va_end(args);
    Serial.println(buffer);
}
