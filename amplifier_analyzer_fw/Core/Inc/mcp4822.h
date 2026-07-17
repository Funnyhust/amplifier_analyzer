#ifndef MCP4822_H
#define MCP4822_H

#include <stdint.h>

#define MCP4822_CHANNEL_A 0U
#define MCP4822_CHANNEL_B 1U
#define MCP4822_GAIN_X1   0U
#define MCP4822_GAIN_X2   1U

typedef enum {
    MCP4822_OK = 0,
    MCP4822_ERROR
} MCP4822_Status_t;

void mcp4822_init(void);
MCP4822_Status_t mcp4822_write_raw(uint8_t channel, uint8_t gain_x2,
                                    uint16_t code);
/* Bounded, register-level transfer intended only for the DAC timer ISR. */
MCP4822_Status_t mcp4822_write_raw_isr(uint8_t channel, uint8_t gain_x2,
                                        uint16_t code);
void mcp4822_flush_isr(void);
void mcp4822_account_dma_error(void);
MCP4822_Status_t mcp4822_set_voltage_mv(uint8_t channel, uint8_t gain_x2,
                                        float voltage_mv);
MCP4822_Status_t mcp4822_shutdown(uint8_t channel, uint8_t gain_x2);
MCP4822_Status_t mcp4822_write_both_sync(uint8_t gain_a_x2,
                                         uint16_t code_a,
                                         uint8_t gain_b_x2,
                                         uint16_t code_b);
uint16_t mcp4822_build_frame(uint8_t channel, uint8_t gain_x2, uint16_t code);
uint32_t mcp4822_get_tx_ok_count(void);
uint32_t mcp4822_get_tx_error_count(void);
uint16_t mcp4822_get_last_frame(void);

#endif /* MCP4822_H */
