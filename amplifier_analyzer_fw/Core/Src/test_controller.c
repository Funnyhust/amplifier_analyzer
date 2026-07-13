#include "test_controller.h"
#include "calibration.h"
#include "protocol.h"
#include "measurement_engine.h"
#include "range_control.h"
#include "mcp4822.h"
#include "ads7861.h"
#include "config.h"
#include <math.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#if defined(STM32F103xB)
#include "stm32f1xx_hal.h"
#elif defined(STM32F407xx)
#include "stm32f4xx_hal.h"
#endif

#ifndef M_PI
#define M_PI 3.14159265358979323846f
#endif

TestState_t current_state = STATE_IDLE;
TestConfig_t current_config;

// Dual ADC buffers and DAC LUT buffers
#define MAX_ADC_BUF 2048
uint32_t adc_dual_buffer[MAX_ADC_BUF]; // Interleaved ADC1/ADC2 samples
uint16_t dac_lut[MAX_ADC_BUF];
uint32_t dac_lut_size = 256;

#if defined(STM32F407xx)
extern DAC_HandleTypeDef hdac;
extern ADC_HandleTypeDef hadc1;
#endif

void test_controller_init(void) {
    current_state = STATE_IDLE;
    
    // Default config
    current_config.wave_type = WAVE_SINE;
    current_config.freq = 20000;       // 20 kHz
    current_config.amp_mv = 300;       // 300 mV
    current_config.offset_mv = 0;      // 0 mV
    current_config.dac_gain = 2;       // X2
    current_config.fs = 200000;        // 200 kSPS
    current_config.samples = 1024;     // 1024 points
    
    calibration_init();
    range_control_init();
    measurement_engine_init();
}

static void test_controller_generate_lut(void) {
    uint32_t N = current_config.fs / current_config.freq;
    if (N < 10) N = 10;
    if (N > MAX_ADC_BUF) N = MAX_ADC_BUF;
    dac_lut_size = N;
    
    for (uint32_t i = 0; i < N; i++) {
        float t = (float)i / N;
        float val = 0.0f;
        
        switch (current_config.wave_type) {
            case WAVE_SINE:
                val = sinf(2.0f * M_PI * t);
                break;
            case WAVE_SQUARE:
                val = (t < 0.5f) ? 1.0f : -1.0f;
                break;
            case WAVE_TRIANGLE:
                val = (t < 0.25f) ? (4.0f * t) :
                      (t < 0.75f) ? (2.0f - 4.0f * t) :
                                    (-4.0f + 4.0f * t);
                break;
            case WAVE_DC:
                val = 0.0f;
                break;
        }
        
        float voltage_mv = val * current_config.amp_mv + current_config.offset_mv;
        dac_lut[i] = calibration_voltage_to_dac_code(voltage_mv, current_config.dac_gain);
    }
}

void test_controller_configure(TestConfig_t *config) {
    memcpy(&current_config, config, sizeof(TestConfig_t));
    test_controller_generate_lut();
}

void test_controller_start(void) {
    if (current_state == STATE_RUNNING) return;
    
    current_state = STATE_RUNNING;

    /* AUTO may recapture after a relay change until the range is stable. */
    for (uint8_t range_attempt = 0U; range_attempt < SIGNAL_RANGE_COUNT;
         range_attempt++) {
    
#if (ACTIVE_MODE == MODE_TEST_USB)
    /*
     * USB-only build: synthesize two ADC channels so the desktop application
     * can exercise CONFIG/START/GET_RESULT/GET_SAMPLES without analog hardware.
     * This entire branch is removed by the preprocessor in every other build.
     */
    const float sim_gain = 0.8f;
    const float sim_phase = -25.0f * M_PI / 180.0f;

    for (uint32_t i = 0; i < current_config.samples; i++) {
        float t = (float)i / current_config.fs;
        float val_in = sinf(2.0f * M_PI * current_config.freq * t);
        float val_out = sim_gain * sinf(2.0f * M_PI * current_config.freq * t
                                       + sim_phase);

        /* Deterministic ripple makes transport/DSP tests more realistic. */
        val_in += 0.005f * sinf(2.0f * M_PI * 7.0f * current_config.freq * t);
        val_out += 0.005f * sinf(2.0f * M_PI * 5.0f * current_config.freq * t);

        float vin_mv = val_in * current_config.amp_mv + current_config.offset_mv;
        float vout_mv = val_out * current_config.amp_mv + current_config.offset_mv;
        uint8_t r = range_control_get_current_range();

        float vin_raw_mv = (vin_mv - calib_coeffs.adc1_c[r]) /
                           calib_coeffs.adc1_m[r] + 1650.0f;
        float vout_raw_mv = (vout_mv - calib_coeffs.adc2_c[r]) /
                            calib_coeffs.adc2_m[r] + 1650.0f;

        int32_t adc_in = (int32_t)(vin_raw_mv * 4095.0f / 3300.0f);
        int32_t adc_out = (int32_t)(vout_raw_mv * 4095.0f / 3300.0f);
        if (adc_in < 0) adc_in = 0;
        if (adc_in > 4095) adc_in = 4095;
        if (adc_out < 0) adc_out = 0;
        if (adc_out > 4095) adc_out = 4095;

        adc_dual_buffer[i] = ((uint32_t)(uint16_t)adc_in << 16) |
                             (uint16_t)adc_out;
    }
#elif defined(STM32F103xB)
    // STM32F103C8T6 Physical SPI path using external MCP4822 and ADS7861
    uint16_t ch1_val = 0;
    uint16_t ch2_val = 0;
    
    for (uint32_t i = 0; i < current_config.samples; i++) {
        float t = (float)i / current_config.fs;
        float val = 0.0f;
        
        switch (current_config.wave_type) {
            case WAVE_SINE:
                val = sinf(2.0f * M_PI * current_config.freq * t);
                break;
            case WAVE_SQUARE:
                {
                    uint32_t per_s = current_config.fs / current_config.freq;
                    val = ((i % per_s) < (per_s / 2)) ? 1.0f : -1.0f;
                }
                break;
            case WAVE_TRIANGLE:
                {
                    uint32_t per_s = current_config.fs / current_config.freq;
                    uint32_t mod = i % per_s;
                    val = (mod < per_s / 2) ? (4.0f * mod / per_s - 1.0f) : (3.0f - 4.0f * mod / per_s);
                }
                break;
            case WAVE_DC:
                val = 0.0f;
                break;
        }
        
        float voltage_mv = val * current_config.amp_mv + current_config.offset_mv;
        
        // Write out to external DAC MCP4822
        mcp4822_set_voltage_mv(0, current_config.dac_gain == 2 ? 1 : 0, voltage_mv);
        
        // Brief settling delay (~4.5 us settling margin)
        for (volatile uint32_t d = 0; d < 40; d++);
        
        // Capture simultaneously on ADS7861
        ads7861_read_pair(&ch1_val, &ch2_val);
        
        // Save to ADC buffer
        adc_dual_buffer[i] = ((uint32_t)ch1_val << 16) | ch2_val;
    }
#else
#error "No capture implementation for this MCU/build mode"
#endif

        measurement_engine_process(adc_dual_buffer, current_config.samples,
                                   current_config.fs, current_config.freq);

        if (!range_control_update_auto_from_samples(adc_dual_buffer,
                                                    current_config.samples)) {
            break;
        }
    }
}

void test_controller_stop(void) {
    current_state = STATE_IDLE;
#if (ACTIVE_MODE == MODE_TEST_USB)
    /* No analog peripheral is driven in the USB-only build. */
#elif defined(STM32F103xB)
    mcp4822_write_raw(0, 0, 0);
    mcp4822_write_raw(1, 0, 0);
#elif defined(STM32F407xx)
    HAL_DAC_SetValue(&hdac, DAC_CHANNEL_1, DAC_ALIGN_12B_R, 0);
#endif
}

void test_controller_get_result(char *out_buf, uint16_t max_len) {
    snprintf(out_buf, max_len, "RESULT:{\"vin_rms\":%.2f,\"vin_vpp\":%.2f,\"vout_rms\":%.2f,\"vout_vpp\":%.2f,\"gain_db\":%.2f,\"phase_deg\":%.2f,\"freq_est\":%.1f,\"range\":%d,\"range_name\":\"%s\",\"range_mode\":\"%s\"}\n",
             last_result.vin_rms, last_result.vin_vpp,
             last_result.vout_rms, last_result.vout_vpp,
             last_result.gain_db, last_result.phase_deg,
             last_result.freq_est, range_control_get_current_range(),
             range_control_get_range_name(), range_control_get_mode_name());
}

void test_controller_get_samples_bin(void) {
    // Send binary packet: 0xaa 0xbb 0x03 [len] [payload] [crc]
    // payload size = samples * 4
    uint16_t chunk_buf[32]; // 64 bytes - safe for stack!
    uint16_t payload_len = (uint16_t)(current_config.samples * 4U);
    
    // Send header: 0xaa 0xbb 0x03 [len_16 big-endian]
    uint8_t header[5];
    header[0] = 0xaa;
    header[1] = 0xbb;
    header[2] = 0x03;
    header[3] = (payload_len >> 8) & 0xff;
    header[4] = payload_len & 0xff;
    
    protocol_send_raw(header, sizeof(header));
    
    uint8_t crc = 0;
    uint32_t samples_sent = 0;
    while (samples_sent < current_config.samples) {
        uint32_t chunk_size = current_config.samples - samples_sent;
        if (chunk_size > 16) chunk_size = 16;
        
        for (uint32_t i = 0; i < chunk_size; i++) {
            uint32_t val = adc_dual_buffer[samples_sent + i];
            uint16_t ch1 = (uint16_t)(val >> 16);
            uint16_t ch2 = (uint16_t)(val & 0xffff);
            
            // Swap to Big-Endian/Vin-first order:
            uint8_t *b = (uint8_t *)&chunk_buf[2*i];
            b[0] = (ch1 >> 8) & 0xff;
            b[1] = ch1 & 0xff;
            b[2] = (ch2 >> 8) & 0xff;
            b[3] = ch2 & 0xff;
            
            crc ^= b[0] ^ b[1] ^ b[2] ^ b[3];
        }
        
        protocol_send_raw((uint8_t*)chunk_buf, chunk_size * 4);
        samples_sent += chunk_size;
    }
    
    protocol_send_raw(&crc, 1);
}
