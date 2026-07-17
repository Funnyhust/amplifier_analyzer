#ifndef TEST_CONTROLLER_H
#define TEST_CONTROLLER_H

#include <stdint.h>

typedef enum {
    STATE_IDLE = 0,
    STATE_RUNNING,
    STATE_ERROR,
    STATE_CALIBRATION
} TestState_t;

typedef enum {
    WAVE_SINE = 0,
    WAVE_SQUARE,
    WAVE_TRIANGLE,
    WAVE_DC
} WaveType_t;

typedef struct {
    WaveType_t wave_type;
    uint32_t freq;       // Hz
    uint32_t amp_mv;     // mV
    int32_t offset_mv;   // mV
    uint8_t dac_gain;    // 1 for X1, 2 for X2
    uint32_t fs;         // Hz
    uint32_t samples;    // block size
} TestConfig_t;

typedef enum {
    TEST_ERROR_NONE = 0,
    TEST_ERROR_DAC_SPI,
    TEST_ERROR_ADC_TIMEOUT,
    TEST_ERROR_ADC_SPI,
    TEST_ERROR_ADC_FRAME,
    TEST_ERROR_ADC_MODE,
    TEST_ERROR_CONFIG_FIELDS,
    TEST_ERROR_DAC_RANGE,
    TEST_ERROR_CAPTURE
} TestError_t;

extern TestState_t current_state;
extern TestConfig_t current_config;

void test_controller_init(void);
void test_controller_service(void);
uint8_t test_controller_configure(const TestConfig_t *config);
uint8_t test_controller_start(void);
TestError_t test_controller_get_last_error(void);
const char *test_controller_get_last_error_text(void);
void test_controller_get_last_adc_words(uint16_t *word_a, uint16_t *word_b);
void test_controller_stop(void);
void test_controller_get_result(char *out_buf, uint16_t max_len);
void test_controller_get_samples_bin(void);
void test_controller_dac_timer_irq(void);
uint8_t test_controller_is_dac_stream_running(void);
uint32_t test_controller_get_dac_update_hz(void);

#endif /* TEST_CONTROLLER_H */
