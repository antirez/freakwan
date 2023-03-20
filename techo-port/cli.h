#ifndef _CLI_H
#define _CLI_H

void cliHandleCommand(const char *cmd, void(*reply_callback)(const char *));

#endif
