#ifndef MCP4822_H
#define MCP4822_H

#include <stdint.h>

void mcp4822_init(void);
void mcp4822_write_raw(uint8_t channel, uint8_t gain_x2, uint16_t code);
void mcp4822_set_voltage_mv(uint8_t channel, uint8_t gain_x2, float voltage_mv);
uint16_t mcp4822_build_frame(uint8_t channel, uint8_t gain_x2, uint16_t code);

#endif /* MCP4822_H */
