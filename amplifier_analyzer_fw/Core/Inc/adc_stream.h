#ifndef ADC_STREAM_H
#define ADC_STREAM_H

#include <stdint.h>
#include "ads7861.h"

typedef struct {
    uint32_t produced;
    uint32_t timer_overrun;
    uint32_t invalid_frame;
    uint32_t ring_overwrite;
    uint32_t requested_fs;
    uint32_t usb_build_cycles_max;
    uint32_t usb_send_cycles_max;
    uint8_t running;
} adc_stream_stats_t;

void adc_stream_init(ads7861_t *dev);
uint8_t adc_stream_start(uint32_t sample_rate_hz);
void adc_stream_stop(void);
void adc_stream_timer_irq(void);
void adc_stream_dma_irq(void);
void adc_stream_get_stats(adc_stream_stats_t *stats);
void adc_stream_set_usb_output(uint8_t enabled);
void adc_stream_usb_service(void);

#endif
