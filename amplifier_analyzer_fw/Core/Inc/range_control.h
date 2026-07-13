#ifndef RANGE_CONTROL_H
#define RANGE_CONTROL_H

#include <stdint.h>

typedef enum {
    SIGNAL_RANGE_0V3 = 0,
    SIGNAL_RANGE_3V3,
    SIGNAL_RANGE_10V,
    SIGNAL_RANGE_COUNT
} SignalRange_t;

typedef enum {
    RANGE_MODE_AUTO = 0,
    RANGE_MODE_MANUAL
} RangeMode_t;

void range_control_init(void);
void range_control_set_range(uint8_t range);
uint8_t range_control_get_current_range(void);
void range_control_set_auto(void);
void range_control_set_manual(uint8_t range);
RangeMode_t range_control_get_mode(void);
const char *range_control_get_range_name(void);
const char *range_control_get_mode_name(void);

/* Returns 1 when the active relay range was changed. */
uint8_t range_control_update_auto_from_samples(const uint32_t *adc_buf,
                                               uint32_t len);

#endif /* RANGE_CONTROL_H */
