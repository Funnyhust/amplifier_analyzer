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
extern ads7861_t g_ads7861;
#elif defined(STM32F407xx)
#include "stm32f4xx_hal.h"
#endif

#ifndef M_PI
#define M_PI 3.14159265358979323846f
#endif

TestState_t current_state = STATE_IDLE;
TestConfig_t current_config;
static TestError_t last_test_error = TEST_ERROR_NONE;
static uint16_t last_adc_word_a = 0U;
static uint16_t last_adc_word_b = 0U;

// Dual ADC buffers and DAC LUT buffers
#define MAX_ADC_BUF 256
#define MAX_DAC_LUT 256
/* MCP4822 settles in about 4.5 us. Keep a 5 us update period so the analog
 * output settles before the next code while timer/DMA handles all transfers. */
#define DAC_MAX_DMA_RATE_HZ 200000U
uint32_t adc_dual_buffer[MAX_ADC_BUF]; // Interleaved ADC1/ADC2 samples
uint16_t dac_lut[MAX_DAC_LUT];
static uint16_t dac_dma_frames[MAX_DAC_LUT] __attribute__((aligned(4)));
static uint32_t dac_cs_set_word = GPIO_PIN_4;
static uint32_t dac_cs_reset_word = (uint32_t)GPIO_PIN_4 << 16;
uint32_t dac_lut_size = 256;
static volatile uint8_t dac_stream_running = 0U;
static volatile uint16_t dac_stream_index = 0U;
static volatile uint8_t dac_stream_start_pending = 0U;
static float last_capture_fs_hz = 0.0f;

#if (ACTIVE_MODE == MODE_TEST_USB)
static float usb_sim_phase = 0.0f;

static void test_controller_update_usb_sim_result(void) {
    const float sim_gain = 0.8f;
    const float inv_sqrt_two = 0.70710678f;
    float amplitude_mv = (float)current_config.amp_mv;

    last_result.vin_mean = (float)current_config.offset_mv;
    last_result.vout_mean = (float)current_config.offset_mv;
    last_result.vin_rms = amplitude_mv * inv_sqrt_two;
    last_result.vout_rms = amplitude_mv * sim_gain * inv_sqrt_two;
    last_result.vin_vpp = 2.0f * amplitude_mv;
    last_result.vout_vpp = 2.0f * amplitude_mv * sim_gain;
    last_result.gain_db = -1.9382f;
    last_result.phase_deg = -25.0f;
    last_result.freq_est = (float)current_config.freq;
}

static void test_controller_generate_usb_sim_frame(void) {
    const float sim_gain = 0.8f;
    const float sim_phase_offset = -25.0f * M_PI / 180.0f;
    const float two_pi = 2.0f * M_PI;
    const float phase_step = fmodf(two_pi * current_config.freq /
                                   current_config.fs, two_pi);
    const float step_sin = sinf(phase_step);
    const float step_cos = cosf(phase_step);
    const float step5_sin = sinf(5.0f * phase_step);
    const float step5_cos = cosf(5.0f * phase_step);
    const float step7_sin = sinf(7.0f * phase_step);
    const float step7_cos = cosf(7.0f * phase_step);
    float in_sin = sinf(usb_sim_phase);
    float in_cos = cosf(usb_sim_phase);
    float out_sin = sinf(usb_sim_phase + sim_phase_offset);
    float out_cos = cosf(usb_sim_phase + sim_phase_offset);
    float harmonic5_sin = sinf(5.0f * usb_sim_phase);
    float harmonic5_cos = cosf(5.0f * usb_sim_phase);
    float harmonic7_sin = sinf(7.0f * usb_sim_phase);
    float harmonic7_cos = cosf(7.0f * usb_sim_phase);

    for (uint32_t i = 0; i < current_config.samples; i++) {
        float val_in = in_sin;
        float val_out = sim_gain * out_sin;

        /* Deterministic ripple makes transport/DSP tests more realistic. */
        val_in += 0.005f * harmonic7_sin;
        val_out += 0.005f * harmonic5_sin;

        float vin_mv = val_in * current_config.amp_mv +
                       current_config.offset_mv;
        float vout_mv = val_out * current_config.amp_mv +
                        current_config.offset_mv;
        uint8_t r = range_control_get_current_range();

        /* Vin is direct; only simulated Vout follows the selected range. */
        float vin_raw_mv = (vin_mv - calib_coeffs.adc1_c[0]) /
                           calib_coeffs.adc1_m[0];
        float vout_raw_mv = (vout_mv - calib_coeffs.adc2_c[r]) /
                            calib_coeffs.adc2_m[r];

        int32_t adc_in = (int32_t)(vin_raw_mv * 2048.0f /
                                   ADS7861_VREF_MV + 2048.0f);
        int32_t adc_out = (int32_t)(vout_raw_mv * 2048.0f /
                                    ADS7861_VREF_MV + 2048.0f);
        if (adc_in < 0) adc_in = 0;
        if (adc_in > 4095) adc_in = 4095;
        if (adc_out < 0) adc_out = 0;
        if (adc_out > 4095) adc_out = 4095;

        adc_dual_buffer[i] = ((uint32_t)(uint16_t)adc_in << 16) |
                             (uint16_t)adc_out;

        float next_sin = in_sin * step_cos + in_cos * step_sin;
        in_cos = in_cos * step_cos - in_sin * step_sin;
        in_sin = next_sin;

        next_sin = out_sin * step_cos + out_cos * step_sin;
        out_cos = out_cos * step_cos - out_sin * step_sin;
        out_sin = next_sin;

        next_sin = harmonic5_sin * step5_cos + harmonic5_cos * step5_sin;
        harmonic5_cos = harmonic5_cos * step5_cos - harmonic5_sin * step5_sin;
        harmonic5_sin = next_sin;

        next_sin = harmonic7_sin * step7_cos + harmonic7_cos * step7_sin;
        harmonic7_cos = harmonic7_cos * step7_cos - harmonic7_sin * step7_sin;
        harmonic7_sin = next_sin;
    }

    usb_sim_phase = fmodf(usb_sim_phase +
                          phase_step * current_config.samples, two_pi);
}
#endif

#if defined(STM32F407xx)
extern DAC_HandleTypeDef hdac;
extern ADC_HandleTypeDef hadc1;
#endif

void test_controller_init(void) {
    current_state = STATE_IDLE;
    last_test_error = TEST_ERROR_NONE;
    last_adc_word_a = 0U;
    last_adc_word_b = 0U;
    
    // Default config
    current_config.wave_type = WAVE_SINE;
    current_config.freq = 20000;       // 20 kHz
    current_config.amp_mv = 300;       // 300 mV
    current_config.offset_mv = 0;      // 0 mV
    current_config.dac_gain = 2;       // X2
    current_config.fs = 200000;        // 200 kSPS
    current_config.samples = 128;      // Must not exceed MAX_ADC_BUF
    
    calibration_init();
    range_control_init();
    measurement_engine_init();
}

static void test_controller_generate_lut(void) {
    uint32_t target_update_hz = DAC_MAX_DMA_RATE_HZ;
    uint32_t N;

    /* ADC Fs and DAC update rate are independent hardware pipelines. Always
     * maximize DAC point density within the analog settling limit; low signal
     * frequencies naturally stop at MAX_DAC_LUT points per period. */
    N = target_update_hz / current_config.freq;

    /* Four points is the minimum that can still represent a sine waveform. */
    if (N < 4U) N = 4U;
    if (N > MAX_DAC_LUT) N = MAX_DAC_LUT;
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
        
        float voltage_mv = DAC_OUTPUT_BIAS_MV +
                           val * current_config.amp_mv +
                           current_config.offset_mv;
        dac_lut[i] = calibration_voltage_to_dac_code(
            voltage_mv, current_config.dac_gain
        );
    }
}

static void test_controller_dac_stream_stop(void) {
#if defined(STM32F103xB) && (ACTIVE_MODE == MODE_NORMAL)
    uint32_t guard = 1000U;
    TIM3->DIER = 0U;
    TIM3->CR1 &= ~TIM_CR1_CEN;
    HAL_NVIC_DisableIRQ(TIM3_IRQn);
    HAL_NVIC_DisableIRQ(DMA1_Channel3_IRQn);
    DMA1_Channel3->CCR &= ~DMA_CCR_EN;
    DMA1_Channel2->CCR &= ~DMA_CCR_EN;
    DMA1_Channel6->CCR &= ~DMA_CCR_EN;
    DMA1->IFCR = DMA_IFCR_CGIF2 | DMA_IFCR_CGIF3 | DMA_IFCR_CGIF6;
    while ((SPI1->SR & SPI_SR_BSY) != 0U && --guard != 0U) {}
    GPIOA->BSRR = GPIO_PIN_4;
    mcp4822_flush_isr();
#endif
    dac_stream_running = 0U;
    dac_stream_index = 0U;
    dac_stream_start_pending = 0U;
}

static uint8_t test_controller_dac_stream_start(void) {
#if defined(STM32F103xB) && (ACTIVE_MODE == MODE_NORMAL)
    uint32_t timer_clock = HAL_RCC_GetPCLK1Freq();
    uint32_t dac_update_hz;
    uint32_t prescaler;
    uint32_t counter_clock;
    uint32_t period_ticks;
    uint8_t gain = current_config.dac_gain == 2U ? MCP4822_GAIN_X2
                                                  : MCP4822_GAIN_X1;

    if (current_config.fs == 0U || current_config.freq == 0U ||
        dac_lut_size == 0U) return 0U;

    /* One complete LUT is exactly one signal period. Low frequencies may hit
     * MAX_DAC_LUT before the 200 kupdate/s ceiling, while higher frequencies
     * use the full timer/DMA rate without changing the configured frequency. */
    if (current_config.freq > UINT32_MAX / dac_lut_size) return 0U;
    dac_update_hz = current_config.freq * dac_lut_size;
    if (mcp4822_write_raw(
            MCP4822_CHANNEL_A,
            gain,
            dac_lut[0]) != MCP4822_OK) {
        return 0U;
    }

    /* APB timer clocks are doubled whenever the APB prescaler is not one. */
    if ((RCC->CFGR & RCC_CFGR_PPRE1) != RCC_CFGR_PPRE1_DIV1) {
        timer_clock *= 2U;
    }

    prescaler = (timer_clock / dac_update_hz - 1U) / 65536U;
    if (prescaler > 65535U) return 0U;
    counter_clock = timer_clock / (prescaler + 1U);
    period_ticks = (counter_clock + dac_update_hz / 2U) / dac_update_hz;
    if (period_ticks < 32U || period_ticks > 65536U) return 0U;

    for (uint32_t i = 0U; i < dac_lut_size; i++) {
        uint32_t source_index = i + 1U;
        if (source_index >= dac_lut_size) source_index = 0U;
        dac_dma_frames[i] = mcp4822_build_frame(
            MCP4822_CHANNEL_A, gain, dac_lut[source_index]);
    }

    __HAL_RCC_TIM3_CLK_ENABLE();
    __HAL_RCC_DMA1_CLK_ENABLE();
    DMA1_Channel3->CCR &= ~DMA_CCR_EN;
    DMA1_Channel2->CCR &= ~DMA_CCR_EN;
    DMA1_Channel6->CCR &= ~DMA_CCR_EN;
    DMA1->IFCR = DMA_IFCR_CGIF2 | DMA_IFCR_CGIF3 | DMA_IFCR_CGIF6;

    DMA1_Channel3->CPAR = (uint32_t)&SPI1->DR;
    DMA1_Channel3->CMAR = (uint32_t)dac_dma_frames;
    DMA1_Channel3->CNDTR = dac_lut_size;
    DMA1_Channel3->CCR = DMA_CCR_DIR | DMA_CCR_MINC | DMA_CCR_CIRC |
                         DMA_CCR_PSIZE_0 | DMA_CCR_MSIZE_0 |
                         DMA_CCR_TEIE | DMA_CCR_PL_0;

    DMA1_Channel6->CPAR = (uint32_t)&GPIOA->BSRR;
    DMA1_Channel6->CMAR = (uint32_t)&dac_cs_set_word;
    DMA1_Channel6->CNDTR = 1U;
    DMA1_Channel6->CCR = DMA_CCR_DIR | DMA_CCR_CIRC |
                         DMA_CCR_PSIZE_1 | DMA_CCR_MSIZE_1 | DMA_CCR_PL_0;

    DMA1_Channel2->CPAR = (uint32_t)&GPIOA->BSRR;
    DMA1_Channel2->CMAR = (uint32_t)&dac_cs_reset_word;
    DMA1_Channel2->CNDTR = 1U;
    DMA1_Channel2->CCR = DMA_CCR_DIR | DMA_CCR_CIRC |
                         DMA_CCR_PSIZE_1 | DMA_CCR_MSIZE_1 | DMA_CCR_PL_0;

    TIM3->CR1 = 0U;
    TIM3->PSC = (uint16_t)prescaler;
    TIM3->ARR = (uint16_t)(period_ticks - 1U);
    TIM3->CCR1 = (uint16_t)(period_ticks / 2U);
    TIM3->CCR3 = (uint16_t)(period_ticks - 8U);
    TIM3->CCMR1 = 0U;
    TIM3->CCMR2 = 0U;
    TIM3->CCER = 0U;
    TIM3->CNT = 0U;
    TIM3->EGR = TIM_EGR_UG;
    TIM3->SR = 0U;

    GPIOA->BSRR = GPIO_PIN_4;
    SPI1->CR1 |= SPI_CR1_SPE;
    DMA1_Channel3->CCR |= DMA_CCR_EN;
    DMA1_Channel2->CCR |= DMA_CCR_EN;
    DMA1_Channel6->CCR |= DMA_CCR_EN;
    dac_stream_running = 1U;
    HAL_NVIC_SetPriority(DMA1_Channel3_IRQn, 1U, 0U);
    HAL_NVIC_EnableIRQ(DMA1_Channel3_IRQn);
    TIM3->DIER = TIM_DIER_UDE | TIM_DIER_CC1DE | TIM_DIER_CC3DE;
    TIM3->CR1 = TIM_CR1_CEN;
    return 1U;
#else
    return 1U;
#endif
}

void test_controller_dac_timer_irq(void) {
#if defined(STM32F103xB) && (ACTIVE_MODE == MODE_NORMAL)
    if ((TIM3->SR & TIM_SR_UIF) == 0U) return;
    TIM3->SR &= ~TIM_SR_UIF;

    if (dac_stream_running != 0U && dac_lut_size != 0U) {
        uint16_t index = dac_stream_index;
        if (mcp4822_write_raw_isr(
                MCP4822_CHANNEL_A,
                current_config.dac_gain == 2U ? MCP4822_GAIN_X2
                                              : MCP4822_GAIN_X1,
                dac_lut[index]) != MCP4822_OK) {
            /* A failed peripheral must not create a permanent IRQ storm. */
            TIM3->DIER &= ~TIM_DIER_UIE;
            TIM3->CR1 &= ~TIM_CR1_CEN;
            dac_stream_running = 0U;
            return;
        }
        index++;
        if (index >= dac_lut_size) index = 0U;
        dac_stream_index = index;
    }
#endif
}

uint8_t test_controller_is_dac_stream_running(void) {
    return dac_stream_running;
}

void test_controller_dac_dma_irq(void) {
#if defined(STM32F103xB) && (ACTIVE_MODE == MODE_NORMAL)
    uint32_t isr = DMA1->ISR;
    if ((isr & DMA_ISR_TEIF3) != 0U) {
        DMA1->IFCR = DMA_IFCR_CGIF3;
        mcp4822_account_dma_error();
        test_controller_dac_stream_stop();
        return;
    }
#endif
}

uint32_t test_controller_get_dac_update_hz(void) {
    if (current_config.freq == 0U || dac_lut_size == 0U ||
        current_config.freq > UINT32_MAX / dac_lut_size) {
        return 0U;
    }
    return current_config.freq * dac_lut_size;
}

uint8_t test_controller_configure(const TestConfig_t *config) {
    uint8_t resume_dac_stream = dac_stream_running;

    if (config == NULL || config->samples == 0U ||
        config->samples > MAX_ADC_BUF || config->freq == 0U ||
        config->freq > (DAC_MAX_DMA_RATE_HZ / 4U) ||
        config->fs < config->freq ||
        (config->dac_gain != 1U && config->dac_gain != 2U)) {
        last_test_error = TEST_ERROR_CONFIG_FIELDS;
        return 0U;
    }

    float excursion_mv = (config->wave_type == WAVE_DC)
                             ? 0.0f : (float)config->amp_mv;
    float minimum_mv = DAC_OUTPUT_BIAS_MV +
                       (float)config->offset_mv - excursion_mv;
    float maximum_mv = DAC_OUTPUT_BIAS_MV +
                       (float)config->offset_mv + excursion_mv;
    float dac_limit_mv = (config->dac_gain == 2U) ? 4095.0f : 2047.5f;
    if (minimum_mv < 0.0f || maximum_mv > dac_limit_mv) {
        last_test_error = TEST_ERROR_DAC_RANGE;
        return 0U;
    }

    /* Rebuild safely, but preserve live-output state when CONFIG is reapplied. */
    test_controller_dac_stream_stop();
    memcpy(&current_config, config, sizeof(TestConfig_t));
    test_controller_generate_lut();
    if (resume_dac_stream != 0U && !test_controller_dac_stream_start()) {
        last_test_error = TEST_ERROR_DAC_SPI;
        return 0U;
    }
    last_test_error = TEST_ERROR_NONE;
    return 1U;
}

uint8_t test_controller_start(void) {
    if (current_state == STATE_RUNNING) {
        /* A repeated START captures a fresh block without resetting DAC phase. */
        current_state = STATE_IDLE;
    }

    if (current_config.samples == 0U ||
        current_config.samples > MAX_ADC_BUF ||
        current_config.fs == 0U || current_config.freq == 0U ||
        dac_lut_size == 0U) {
        last_test_error = TEST_ERROR_CONFIG_FIELDS;
        current_state = STATE_ERROR;
        return 0U;
    }
    
    current_state = STATE_RUNNING;
    last_test_error = TEST_ERROR_NONE;

#if defined(STM32F103xB) && (ACTIVE_MODE == MODE_NORMAL)
    test_controller_generate_lut();
    if (dac_stream_running == 0U && !test_controller_dac_stream_start()) {
        last_test_error = TEST_ERROR_DAC_SPI;
        current_state = STATE_ERROR;
        return 0U;
    }
#endif

#if (ACTIVE_MODE == MODE_TEST_USB)
    usb_sim_phase = 0.0f;
#endif

    /* AUTO may recapture after a relay change until the range is stable. */
    for (uint8_t range_attempt = 0U; range_attempt < SIGNAL_RANGE_COUNT;
         range_attempt++) {
    
#if (ACTIVE_MODE == MODE_TEST_USB)
    /*
     * USB-only build: synthesize two ADC channels so the desktop application
     * can exercise CONFIG/START/GET_RESULT/GET_SAMPLES without analog hardware.
     * This entire branch is removed by the preprocessor in every other build.
     */
    test_controller_generate_usb_sim_frame();
#elif defined(STM32F103xB)
    // STM32F103C8T6 Physical SPI path using external MCP4822 and ADS7861
    ads7861_sample_pair_t adc_sample;
    uint32_t capture_started = DWT->CYCCNT;
    
    for (uint32_t i = 0; i < current_config.samples; i++) {
        // Capture simultaneously on ADS7861
        ads7861_status_t adc_status = ADS7861_OK;
        uint8_t frame_attempt;
        for (frame_attempt = 0U; frame_attempt < 3U; frame_attempt++) {
            adc_status = ads7861_read_pair(
                &g_ads7861, ADS7861_PAIR_0, &adc_sample);
            last_adc_word_a = adc_sample.word_a;
            last_adc_word_b = adc_sample.word_b;
            if (adc_status != ADS7861_OK || adc_sample.valid != 0U) {
                break;
            }
        }
        if (adc_status != ADS7861_OK) {
            if (adc_status == ADS7861_ERR_TIMEOUT) {
                last_test_error = TEST_ERROR_ADC_TIMEOUT;
            } else if (adc_status == ADS7861_ERR_SPI) {
                last_test_error = TEST_ERROR_ADC_SPI;
            } else if (adc_status == ADS7861_ERR_INVALID_MODE) {
                last_test_error = TEST_ERROR_ADC_MODE;
            } else {
                last_test_error = TEST_ERROR_CAPTURE;
            }
            current_state = STATE_ERROR;
            test_controller_dac_stream_stop();
            return 0U;
        }
        if (adc_sample.valid == 0U) {
            last_test_error = TEST_ERROR_ADC_FRAME;
            current_state = STATE_ERROR;
            test_controller_dac_stream_stop();
            return 0U;
        }
        
        /*
         * The existing USB/measurement pipeline uses 12-bit offset-binary.
         * Convert the ADS7861 signed two's-complement samples at this boundary;
         * the standalone driver always exposes the original signed values.
         */
        /* Board wiring: ADS B0 is Vin; ADS A0 is Vout. */
        uint16_t vin_code = (uint16_t)((int32_t)adc_sample.ch_b_raw + 2048);
        uint16_t vout_code = (uint16_t)((int32_t)adc_sample.ch_a_raw + 2048);
        adc_dual_buffer[i] = ((uint32_t)vin_code << 16) | vout_code;
    }
    {
        uint32_t elapsed_cycles = DWT->CYCCNT - capture_started;
        if (elapsed_cycles != 0U) {
            last_capture_fs_hz =
                ((float)current_config.samples * (float)SystemCoreClock) /
                (float)elapsed_cycles;
        }
    }
#else
#error "No capture implementation for this MCU/build mode"
#endif

#if (ACTIVE_MODE == MODE_TEST_USB)
        test_controller_update_usb_sim_result();
#else
        uint32_t processing_fs = (last_capture_fs_hz >= 1.0f)
                               ? (uint32_t)(last_capture_fs_hz + 0.5f)
                               : current_config.fs;
        measurement_engine_process(adc_dual_buffer, current_config.samples,
                                   processing_fs, current_config.freq);
#endif

        if (!range_control_update_auto_from_samples(adc_dual_buffer,
                                                    current_config.samples)) {
            break;
        }
    }
    if (current_state == STATE_ERROR) return 0U;

    return 1U;
}

void test_controller_service(void) {
#if defined(STM32F103xB) && (ACTIVE_MODE == MODE_NORMAL)
    if (dac_stream_start_pending == 0U) return;

    dac_stream_start_pending = 0U;
    if (current_state == STATE_RUNNING &&
        test_controller_dac_stream_start() == 0U) {
        last_test_error = TEST_ERROR_CAPTURE;
        current_state = STATE_ERROR;
    }
#endif
}

TestError_t test_controller_get_last_error(void) {
    return last_test_error;
}

const char *test_controller_get_last_error_text(void) {
    switch (last_test_error) {
        case TEST_ERROR_NONE:        return "NONE";
        case TEST_ERROR_DAC_SPI:     return "DAC_SPI";
        case TEST_ERROR_ADC_TIMEOUT: return "ADC_TIMEOUT";
        case TEST_ERROR_ADC_SPI:     return "ADC_SPI";
        case TEST_ERROR_ADC_FRAME:   return "ADC_FRAME";
        case TEST_ERROR_ADC_MODE:    return "ADC_MODE";
        case TEST_ERROR_CONFIG_FIELDS:return "CONFIG_FIELDS";
        case TEST_ERROR_DAC_RANGE:   return "DAC_RANGE";
        default:                     return "CAPTURE_FAILED";
    }
}

void test_controller_get_last_adc_words(uint16_t *word_a, uint16_t *word_b) {
    if (word_a != NULL) *word_a = last_adc_word_a;
    if (word_b != NULL) *word_b = last_adc_word_b;
}

void test_controller_stop(void) {
    current_state = STATE_IDLE;
    test_controller_dac_stream_stop();
#if (ACTIVE_MODE == MODE_TEST_USB)
    /* No analog peripheral is driven in the USB-only build. */
#elif defined(STM32F103xB)
    mcp4822_shutdown(MCP4822_CHANNEL_A, MCP4822_GAIN_X2);
    mcp4822_shutdown(MCP4822_CHANNEL_B, MCP4822_GAIN_X2);
#elif defined(STM32F407xx)
    HAL_DAC_SetValue(&hdac, DAC_CHANNEL_1, DAC_ALIGN_12B_R, 0);
#endif
}

void test_controller_get_result(char *out_buf, uint16_t max_len) {
    /* JSON has no NaN/Infinity literals. Never leak non-finite DSP values. */
    float vin_rms = isfinite(last_result.vin_rms) ? last_result.vin_rms : 0.0f;
    float vin_vpp = isfinite(last_result.vin_vpp) ? last_result.vin_vpp : 0.0f;
    float vout_rms = isfinite(last_result.vout_rms) ? last_result.vout_rms : 0.0f;
    float vout_vpp = isfinite(last_result.vout_vpp) ? last_result.vout_vpp : 0.0f;
    float gain_db = isfinite(last_result.gain_db) ? last_result.gain_db : -99.0f;
    float phase_deg = isfinite(last_result.phase_deg) ? last_result.phase_deg : 0.0f;
    float freq_est = isfinite(last_result.freq_est) ? last_result.freq_est : 0.0f;

    snprintf(out_buf, max_len, "RESULT:{\"vin_rms\":%.2f,\"vin_vpp\":%.2f,\"vout_rms\":%.2f,\"vout_vpp\":%.2f,\"gain_db\":%.2f,\"phase_deg\":%.2f,\"freq_est\":%.1f,\"fs_actual\":%.1f,\"range\":%d,\"range_name\":\"%s\",\"range_mode\":\"%s\"}\n",
             vin_rms, vin_vpp, vout_rms, vout_vpp,
             gain_db, phase_deg, freq_est, last_capture_fs_hz,
             range_control_get_current_range(),
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

#if (ACTIVE_MODE == MODE_TEST_USB)
    /* Prepare the next phase-continuous frame after this one is fully sent. */
    if (current_state == STATE_RUNNING) {
        test_controller_generate_usb_sim_frame();
        test_controller_update_usb_sim_result();
    }
#endif
}
