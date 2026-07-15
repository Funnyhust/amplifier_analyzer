#ifndef CALIBRATION_H
#define CALIBRATION_H

#include <stdint.h>

typedef struct {
    float dac_a;
    float dac_b;
    float adc1_m[3]; // 3 ranges: 00 (x1), 01 (/10), 10 (/100)
    float adc1_c[3];
    float adc2_m[3];
    float adc2_c[3];
} CalibCoeffs_t;

extern CalibCoeffs_t calib_coeffs;

void calibration_init(void);
void calibration_set(const char *key, float val);
float calibration_get(const char *key);
void calibration_save(void);
void calibration_reset(void);

// Apply calibration
uint16_t calibration_voltage_to_dac_code(float voltage_mv, uint8_t gain);
float calibration_adc_code_to_voltage(uint16_t code, uint8_t channel, uint8_t range);

#endif /* CALIBRATION_H */
