#ifndef ADS7861_H
#define ADS7861_H

#include <stdint.h>

void ads7861_init(void);
void ads7861_start_conversion(void);
uint16_t ads7861_read_raw(uint8_t channel);
void ads7861_read_pair(uint16_t *ch1, uint16_t *ch2);
float ads7861_raw_to_voltage(uint16_t code, uint8_t range);

#endif /* ADS7861_H */
