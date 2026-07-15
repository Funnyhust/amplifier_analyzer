#include "measurement_engine.h"
#include "calibration.h"
#include "range_control.h"
#include <math.h>
#include <string.h>

MeasurementResult_t last_result;

// Static buffers to avoid stack overflow
#define MAX_MEASURE_SAMPLES 2048
static float vin_f[MAX_MEASURE_SAMPLES];
static float vout_f[MAX_MEASURE_SAMPLES];

void measurement_engine_init(void) {
    memset(&last_result, 0, sizeof(MeasurementResult_t));
}

void measurement_engine_process(uint16_t *adc_buf, uint32_t len, uint32_t fs, uint32_t signal_freq) {
    if (len > MAX_MEASURE_SAMPLES) len = MAX_MEASURE_SAMPLES;
    if (len == 0) return;
    
    uint8_t r = range_control_get_current_range();
    
    // 1. Convert to voltage (mV) and calculate mean/min/max
    float sum_in = 0.0f;
    float sum_out = 0.0f;
    float min_in = 1e9f, max_in = -1e9f;
    float min_out = 1e9f, max_out = -1e9f;
    
    for (uint32_t i = 0; i < len; i++) {
        vin_f[i] = calibration_adc_code_to_voltage(adc_buf[2*i], 1, r);
        vout_f[i] = calibration_adc_code_to_voltage(adc_buf[2*i+1], 2, r);
        
        sum_in += vin_f[i];
        sum_out += vout_f[i];
        
        if (vin_f[i] < min_in) min_in = vin_f[i];
        if (vin_f[i] > max_in) max_in = vin_f[i];
        
        if (vout_f[i] < min_out) min_out = vout_f[i];
        if (vout_f[i] > max_out) max_out = vout_f[i];
    }
    
    float mean_in = sum_in / len;
    float mean_out = sum_out / len;
    
    last_result.vin_mean = mean_in;
    last_result.vout_mean = mean_out;
    last_result.vin_vpp = max_in - min_in;
    last_result.vout_vpp = max_out - min_out;
    
    // 2. Subtract mean and calculate AC RMS
    float sq_sum_in = 0.0f;
    float sq_sum_out = 0.0f;
    
    for (uint32_t i = 0; i < len; i++) {
        float ac_in = vin_f[i] - mean_in;
        float ac_out = vout_f[i] - mean_out;
        
        // Zero-mean the buffer in place for cross-correlation
        vin_f[i] = ac_in;
        vout_f[i] = ac_out;
        
        sq_sum_in += ac_in * ac_in;
        sq_sum_out += ac_out * ac_out;
    }
    
    float rms_in = sqrtf(sq_sum_in / len);
    float rms_out = sqrtf(sq_sum_out / len);
    
    last_result.vin_rms = rms_in;
    last_result.vout_rms = rms_out;
    
    // 3. Gain calculation (in dB)
    if (rms_in > 0.01f) {
        float gain = rms_out / rms_in;
        last_result.gain_db = 20.0f * log10f(gain);
    } else {
        last_result.gain_db = -99.0f;
    }
    
    // 4. Cross correlation for phase shift
    int32_t n_per = (int32_t)((float)fs / (float)signal_freq);
    if (n_per < 5) n_per = 5;
    if (n_per > (int32_t)len / 4) n_per = (int32_t)len / 4;
    
    float max_corr = -1e30f;
    int32_t best_lag = 0;
    
    for (int32_t k = -n_per; k <= n_per; k++) {
        float corr = 0.0f;
        int32_t count = 0;
        for (int32_t n = 0; n < (int32_t)len; n++) {
            int32_t y_idx = n + k;
            if (y_idx >= 0 && y_idx < (int32_t)len) {
                corr += vin_f[n] * vout_f[y_idx];
                count++;
            }
        }
        if (count > 0) {
            corr /= count;
        }
        if (corr > max_corr) {
            max_corr = corr;
            best_lag = k;
        }
    }
    
    float phase = (float)best_lag * ((float)signal_freq / (float)fs) * 360.0f;
    while (phase > 180.0f) phase -= 360.0f;
    while (phase < -180.0f) phase += 360.0f;
    
    last_result.phase_deg = phase;
    last_result.freq_est = (float)signal_freq; // Keep simplified or can do zero crossing
}
