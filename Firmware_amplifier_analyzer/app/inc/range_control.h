#ifndef RANGE_CONTROL_H
#define RANGE_CONTROL_H

#include <stdint.h>

void range_control_init(void);
void range_control_set_range(uint8_t range);
uint8_t range_control_get_current_range(void);
void range_control_update_auto(float vpp_mv);

#endif /* RANGE_CONTROL_H */
