#ifndef ADS7861_H
#define ADS7861_H

#include <stdint.h>

#if defined(STM32F103xB)
#include "stm32f1xx_hal.h"
#elif defined(STM32F407xx)
#include "stm32f4xx_hal.h"
#else
#error "ADS7861: add the STM32 HAL header for this target"
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define ADS7861_DEFAULT_VREF             2.5f
#define ADS7861_DEFAULT_TIMEOUT_US       100U

/* Set to 0 only for early bring-up when BUSY is not wired or not trustworthy. */
#ifndef ADS7861_USE_BUSY_PIN
#define ADS7861_USE_BUSY_PIN             0
#endif

/* Deterministic slow GPIO clock for first-board bring-up. Set to 0 later. */
#ifndef ADS7861_USE_BITBANG_BRINGUP
#define ADS7861_USE_BITBANG_BRINGUP      1
#endif

#ifndef ADS7861_BITBANG_HALF_PERIOD_US
#define ADS7861_BITBANG_HALF_PERIOD_US   1U
#endif

/* Temporary: accept live non-stuck words while board framing is characterized. */
#ifndef ADS7861_RELAX_FRAME_VALIDATION
#define ADS7861_RELAX_FRAME_VALIDATION   1
#endif

typedef enum {
    ADS7861_OK = 0,
    ADS7861_ERR_NULL,
    ADS7861_ERR_TIMEOUT,
    ADS7861_ERR_SPI,
    ADS7861_ERR_INVALID_MODE
} ads7861_status_t;

typedef enum {
    ADS7861_PAIR_0 = 0,   /* A0/B0 */
    ADS7861_PAIR_1 = 1    /* A1/B1 */
} ads7861_pair_t;

typedef enum {
    ADS7861_MODE_TWO_CH_SERIAL_A_ONLY,
    ADS7861_MODE_TWO_CH_DUAL_SERIAL,
    ADS7861_MODE_FOUR_CH_SERIAL_A_ONLY,
    ADS7861_MODE_FOUR_CH_DUAL_SERIAL
} ads7861_mode_t;

typedef struct {
    int16_t ch_a_raw;
    int16_t ch_b_raw;
    uint16_t word_a;
    uint16_t word_b;
    uint8_t status_a;
    uint8_t status_b;
    uint8_t valid;
} ads7861_sample_pair_t;

typedef struct {
    SPI_HandleTypeDef *hspi;
    GPIO_TypeDef *cs_port;
    uint16_t cs_pin;
    GPIO_TypeDef *convst_port;
    uint16_t convst_pin;
    GPIO_TypeDef *busy_port;
    uint16_t busy_pin;
    GPIO_TypeDef *a0_port;
    uint16_t a0_pin;
    GPIO_TypeDef *m0_port;
    uint16_t m0_pin;
    GPIO_TypeDef *m1_port;
    uint16_t m1_pin;
    GPIO_TypeDef *clock_port;
    uint16_t clock_pin;
    GPIO_TypeDef *data_port;
    uint16_t data_pin;
    float vref;
    uint32_t timeout_us;

    /* Driver state; keep these fields when copying the configuration. */
    ads7861_mode_t mode;
    ads7861_pair_t pair;
} ads7861_t;

ads7861_status_t ads7861_init(
    ads7861_t *dev,
    SPI_HandleTypeDef *hspi,
    GPIO_TypeDef *cs_port, uint16_t cs_pin,
    GPIO_TypeDef *convst_port, uint16_t convst_pin,
    GPIO_TypeDef *busy_port, uint16_t busy_pin,
    GPIO_TypeDef *a0_port, uint16_t a0_pin,
    GPIO_TypeDef *m0_port, uint16_t m0_pin,
    GPIO_TypeDef *m1_port, uint16_t m1_pin,
    GPIO_TypeDef *clock_port, uint16_t clock_pin,
    GPIO_TypeDef *data_port, uint16_t data_pin);

ads7861_status_t ads7861_set_mode(ads7861_t *dev, ads7861_mode_t mode);
ads7861_status_t ads7861_select_pair(ads7861_t *dev, ads7861_pair_t pair);
ads7861_status_t ads7861_start_conversion(ads7861_t *dev);
ads7861_status_t ads7861_wait_busy_done(ads7861_t *dev);
ads7861_status_t ads7861_read_words_serial_a(
    ads7861_t *dev, uint16_t *word_a, uint16_t *word_b);
ads7861_status_t ads7861_read_pair(
    ads7861_t *dev, ads7861_pair_t pair, ads7861_sample_pair_t *sample);

/*
 * Word: [15]=channel 0/1, [14]=A/B, [13:2]=signed 12-bit data, [1:0]=0.
 * status_ch/status_ab may be NULL. Return value is -2048..+2047.
 */
int16_t ads7861_parse_word(
    uint16_t word, uint8_t *status_ch, uint8_t *status_ab);

/* Differential voltage only; no common-mode voltage is added. */
float ads7861_raw_to_voltage(const ads7861_t *dev, int16_t raw);
ads7861_status_t ads7861_read_voltage_pair(
    ads7861_t *dev, ads7861_pair_t pair, float *voltage_a, float *voltage_b);

ads7861_status_t ads7861_self_test_parse(void);

#ifdef __cplusplus
}
#endif

#endif /* ADS7861_H */
