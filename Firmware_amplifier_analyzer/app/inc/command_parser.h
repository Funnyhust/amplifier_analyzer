#ifndef COMMAND_PARSER_H
#define COMMAND_PARSER_H

#include <stdint.h>

void command_parser_init(void);
void command_parser_feed_char(uint8_t ch);
void command_parser_execute(char *cmd_line);

#endif /* COMMAND_PARSER_H */
