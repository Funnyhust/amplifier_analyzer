#ifndef MEASUREMENT_ENGINE_H
#define MEASUREMENT_ENGINE_H

#include <stdint.h>

typedef struct {
    float vin_mean;
    float vin_rms;
    float vin_vpp;
    float vout_mean;
    float vout_rms;
    float vout_vpp;
    float gain_db;
    float phase_deg;
    float freq_est;
} MeasurementResult_t;

extern MeasurementResult_t last_result;

void measurement_engine_init(void);
void measurement_engine_process(uint16_t *adc_buf, uint32_t len, uint32_t fs, uint32_t signal_freq);

#endif /* MEASUREMENT_ENGINE_H */
