#include <ctype.h>
#include <string.h>
#include <stdlib.h>
#include <stdarg.h>

#include "proto.h"
#include "settings.h"
#include "eink.h"
#include "log.h"

/* ========================= Arguments splitting code ======================= */

/* Special return value for empty argument vector, in order to
 * take it apart from NULL (used to signal errors) without the need
 * of allocating anything. */
static const char *cliSplitArgsEmpty[1] = {
    "BUG: accessing zero items array returned by cliSplitArgs()"
};

/* Helper function for cliSplitArgs() that converts a hex digit into an
 * integer from 0 to 15 */
static int hex_digit_to_int(char c) {
    c = tolower(c);
    if (c >= '0' && c <= '9') return c-'0';
    if (c >= 'a' && c <= 'f') return c-'a';
    return -1;
}

static int is_hex_digit(char c) {
    return hex_digit_to_int(c) != -1;
}

/* Split a text line into arguments, where every argument can be in the
 * following programming-language REPL-alike form:
 *
 * arg1 "some argument with spaces" "And escapes, too\n\xff" 1 2 3
 *
 * The number of arguments found is stored into *argc, and an array
 * of heap-allocated C strings returned as an array.
 *
 * The caller should free the resulting array calling cliFreeArgs().
 *
 * On syntax error or OOM, NULL is returned.
 *
 * NOTE about limitations: This function was rewritten (from some other
 * code of mine) for embedded systems, it can only handle a maximum of
 * CLI_MAX_ARG_LEN arguments length for a total of CLI_MAX_ARG_NUM. Thanks
 * to this limitation, the function will be faster and will cause less
 * reallocations and memory fragmentation.
 *
 * If the number of tokens limit is reached, the function returns NULL.
 */

#define CLI_MAX_ARG_LEN 256
#define CLI_MAX_ARG_NUM 32
char **cliSplitArgs(const char *line, int *argc) {
    const char *p = line;
    char cur[CLI_MAX_ARG_LEN]; // Current token we are splitting.
    int len = 0; // Length of the current token.
    char **vector = NULL;

    *argc = 0;
    while(*argc < CLI_MAX_ARG_NUM) {
        /* skip blanks */
        while(*p && isspace(*p)) p++;
        if (*p) {
            /* get a token */
            int inq=0;  /* set to 1 if we are in "quotes" */
            int insq=0; /* set to 1 if we are in 'single quotes' */
            int done=0;

            while(!done && len < CLI_MAX_ARG_LEN) {
                if (inq) {
                    if (*p == '\\' && *(p+1) == 'x' &&
                                             is_hex_digit(*(p+2)) &&
                                             is_hex_digit(*(p+3)))
                    {
                        unsigned char byteval;

                        byteval = (hex_digit_to_int(*(p+2))*16)+
                                   hex_digit_to_int(*(p+3));
                        cur[len++] = byteval;
                        p += 3;
                    } else if (*p == '\\' && *(p+1)) {
                        char c;

                        p++;
                        switch(*p) {
                        case 'n': c = '\n'; break;
                        case 'r': c = '\r'; break;
                        case 't': c = '\t'; break;
                        case 'b': c = '\b'; break;
                        case 'a': c = '\a'; break;
                        default: c = *p; break;
                        }
                        cur[len++] = c;
                    } else if (*p == '"') {
                        /* closing quote must be followed by a space or
                         * nothing at all. */
                        if (*(p+1) && !isspace(*(p+1))) goto err;
                        done=1;
                    } else if (!*p) {
                        /* unterminated quotes */
                        goto err;
                    } else {
                        /* Normal character inside quotes. */
                        cur[len++] = *p;
                    }
                } else if (insq) {
                    if (*p == '\\' && *(p+1) == '\'') {
                        p++;
                        cur[len++] = '\'';
                    } else if (*p == '\'') {
                        /* closing quote must be followed by a space or
                         * nothing at all. */
                        if (*(p+1) && !isspace(*(p+1))) goto err;
                        done=1;
                    } else if (!*p) {
                        /* unterminated quotes */
                        goto err;
                    } else {
                        /* Normal character inside single quotes. */
                        cur[len++] = *p;
                    }
                } else {
                    switch(*p) {
                    case ' ':
                    case '\n':
                    case '\r':
                    case '\t':
                    case '\0':
                        done=1;
                        break;
                    case '"':
                        inq=1;
                        break;
                    case '\'':
                        insq=1;
                        break;
                    default:
                        cur[len++] = *p;
                        break;
                    }
                }
                if (*p) p++;
            }
            /* add the token to the vector */
            if (vector == NULL) {
                vector = (char**)malloc(sizeof(char*)*CLI_MAX_ARG_NUM);
                if (vector == NULL) return NULL;
                memset(vector,0,sizeof(char*)*CLI_MAX_ARG_NUM);
            }
            vector[*argc] = (char*)malloc(len+1);
            memcpy(vector[*argc],cur,len);
            vector[*argc][len] = 0;
            (*argc)++;
            len = 0;
        } else {
            /* Empty input string? Return non-null to avoid signaling an
             * error. Argc is zero, so the return value is invalid to access,
             * in theory, but can be freed. */
            if (vector == NULL) vector = (char**)cliSplitArgsEmpty;
            return vector;
        }
    }

err:
    while((*argc)--)
        free(vector[*argc]);
    free(vector);
    *argc = 0;
    return NULL;
}

void cliFreeArgs(char **argv, int argc) {
    if (argv == cliSplitArgsEmpty) return;
    for (int j = 0; j < argc; j++) free(argv[j]);
    free(argv);
}

/* ========================== CLI commands helpers ========================== */

/* Invoke the CLI reply callback with the string composed using printf-alike
 * format. */
void cliReplyPrintf(void(*reply_callback)(const char*),const char *fmt,...) {
    char buffer[256];
    va_list args;
    va_start(args, fmt);
    int len = vsnprintf(buffer, sizeof(buffer), fmt, args);
    va_end(args);
    reply_callback(buffer);
}

/* ========================= CLI commands callbacks ========================= */

/* Settings that are just boolean values that can be turned on/off all need
 * the same code, so we abstract away their handling in this function. */
void cliCommandBoolSetting(const char **argv, int argc, void(*reply_callback)(const char*), void *aux) {
    bool *field = (bool*)aux;
    const char *name = argv[0];
    if (argc != 1 && argc != 2) {
        cliReplyPrintf(reply_callback,"Wrong # of args for setting: %s", name);
        return;
    }
    if (argc == 2) {
        bool newval = !strcasecmp(argv[1],"1") ||
                      !strcasecmp(argv[1],"true");
        *field = newval;
    }
    cliReplyPrintf(reply_callback,"%s is set to %d", name, *field ? 1 : 0);
}

/* !loglevel <level> */
void cliCommandLogLevel(const char **argv, int argc, void(*reply_callback)(const char*), void *aux) {
    reply_callback(fwSetLogLevel(argv[1]) == true ?
        "Ok" : "Invalid log level");
}

/* !help */
void cliCommandHelp(const char **argv, int argc, void(*reply_callback)(const char*), void *aux) {
    const char *help[] = {
"!automsg on|off",
"!loglevel warning|info|verbose|debug|tracing",
NULL
    };
    for (int j = 0; help[j]; j++)
        reply_callback(help[j]);
}

/* !bw */
void cliCommandBw(const char **argv, int argc, void(*reply_callback)(const char*), void *aux) {
    int valid_bws[] = {7800,10400,15600,20800,31250,41700,
                     62500,125000,250000,500000,0};
    if (argc > 1) {
        int bw = atoi(argv[1]), j;
        for (j = 0; valid_bws[j]; j++) {
            if (valid_bws[j] == bw) break;
        }
        if (valid_bws[j] == 0) {
            cliReplyPrintf(reply_callback,"Invalid bandwidth %s", argv[1]);
            return;
        }
        FW.lora_bw = bw / 1000;
        setLoRaParams();
    }
    cliReplyPrintf(reply_callback,"Bandwidth set to %d", FW.lora_bw);
}

/* ====================== Commands table and dispatch ======================= */

#define NUMARGS_MAX 0xffff // Any high value will do.

struct {
    const char *name;           // Command name.
    int min_args, max_args;     // Minimum and maximum number of arguments.
    void(*callback)(const char **argv, int argc, void(*reply_callback)(const char*),void*);                     // Callback implementing the command
    void *aux;                  // Aux data the command may require, such as
                                // a reference to a global setting.
} CliCommandTable[] = {
    {"automsg",  1, 2, cliCommandBoolSetting, (void*)&FW.automsg},
    {"loglevel", 2, 2, cliCommandLogLevel, NULL},
    {"bw", 1, 2, cliCommandBw, NULL},
    {"help", 1, NUMARGS_MAX, cliCommandHelp, NULL},
    {NULL,0,0,NULL,NULL}    // End of commands.
};

void cliHandleCommand(const char *cmd, void(*reply_callback)(const char *)) {
    if (cmd[0] == '!') {
        int argc;
        char **argv = cliSplitArgs(cmd+1,&argc);
        if (argv == NULL) {
            reply_callback("Syntax error");
            return;
        }

        if (argc == 0) {
            cliFreeArgs(argv,argc);
            return;
        }

        for (int j = 0; CliCommandTable[j].name; j++) {
            if (!strcasecmp(argv[0],CliCommandTable[j].name) && 
                argc >= CliCommandTable[j].min_args &&
                argc <= CliCommandTable[j].max_args)
            {
                CliCommandTable[j].callback((const char**)argv,argc,reply_callback,CliCommandTable[j].aux);
                return;
            }
        }
        reply_callback("Unknown command or wrong number of arguments");
    } else {
        protoSendDataMessage(FW.nick,cmd,strlen(cmd),0);
        char msg[128];
        snprintf(msg,sizeof(msg),"you> %s",cmd);
        displayPrint(msg);
    }
}

#ifdef TEST_MAIN
#include <stdio.h>
int main(void) {
    while(1) {
        char buf[1024];
        fgets(buf,sizeof(buf),stdin);
        int numargs;
        char **res = cliSplitArgs(buf,&numargs);
        printf("Args: %d\n", numargs);
        for (int j = 0; j < numargs; j++) {
            printf("%s\n", res[j]);
        }
        cliFreeArgs(res,numargs);
    }
    return 0;
}
#endif
