#include "range_control.h"
#include "config.h"
#if defined(STM32F103xB)
#include "stm32f1xx_hal.h"
#elif defined(STM32F407xx)
#include "stm32f4xx_hal.h"
#endif

/* Relay drivers from the schematic. All three are active-high. */
#if (ACTIVE_MODE != MODE_TEST_USB)
#define RELAY_0V3_PORT GPIOA
#define RELAY_0V3_PIN  GPIO_PIN_15
#define RELAY_3V3_PORT GPIOB
#define RELAY_3V3_PIN  GPIO_PIN_3
#define RELAY_10V_PORT GPIOB
#define RELAY_10V_PIN  GPIO_PIN_4
#endif

/* ADC is 12-bit. Leave margin for noise and analog output saturation. */
#define ADC_RAIL_LOW_CODE       128U
#define ADC_RAIL_HIGH_CODE      3967U
#define ADC_RAIL_HIT_PERCENT    2U
#define ADC_MIDSCALE_CODE       2048U
#define ADC_10V_TO_3V3_PEAK     650U
#define ADC_3V3_TO_0V3_PEAK     300U
#define AUTO_OVERRANGE_BLOCKS   1U
#define AUTO_UNDERRANGE_BLOCKS  1U

/* Approximate relay release/operate interval at 72 MHz, without HAL_Delay(). */
#if (ACTIVE_MODE != MODE_TEST_USB)
#define RELAY_SETTLE_CYCLES     180000U
#endif

static uint8_t current_range = SIGNAL_RANGE_10V;
static RangeMode_t current_mode = RANGE_MODE_AUTO;
static uint8_t overrange_blocks = 0U;
static uint8_t underrange_blocks = 0U;

#if (ACTIVE_MODE != MODE_TEST_USB)
static void relay_delay(void) {
    for (volatile uint32_t i = 0; i < RELAY_SETTLE_CYCLES; i++);
}

static void relays_all_off(void) {
    HAL_GPIO_WritePin(RELAY_0V3_PORT, RELAY_0V3_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(RELAY_3V3_PORT, RELAY_3V3_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(RELAY_10V_PORT, RELAY_10V_PIN, GPIO_PIN_RESET);
}

static void relay_enable(uint8_t range) {
    if (range == SIGNAL_RANGE_0V3) {
        HAL_GPIO_WritePin(RELAY_0V3_PORT, RELAY_0V3_PIN, GPIO_PIN_SET);
    } else if (range == SIGNAL_RANGE_3V3) {
        HAL_GPIO_WritePin(RELAY_3V3_PORT, RELAY_3V3_PIN, GPIO_PIN_SET);
    } else {
        HAL_GPIO_WritePin(RELAY_10V_PORT, RELAY_10V_PIN, GPIO_PIN_SET);
    }
}
#endif

void range_control_init(void) {
    current_mode = RANGE_MODE_AUTO;
    current_range = SIGNAL_RANGE_COUNT;
    overrange_blocks = 0U;
    underrange_blocks = 0U;

    /* Start at the widest range to protect the ADC from an unknown input. */
    range_control_set_range(SIGNAL_RANGE_10V);
}

void range_control_set_range(uint8_t range) {
    if (range >= SIGNAL_RANGE_COUNT) {
        return;
    }

    if (range == current_range) {
        return;
    }

    /* Break-before-make: never energize two feedback relays together. */
#if (ACTIVE_MODE != MODE_TEST_USB)
    relays_all_off();
    relay_delay();
    relay_enable(range);
    relay_delay();
#endif

    current_range = range;
    overrange_blocks = 0U;
    underrange_blocks = 0U;
}

uint8_t range_control_get_current_range(void) {
    return current_range;
}

void range_control_set_auto(void) {
    current_mode = RANGE_MODE_AUTO;
    overrange_blocks = 0U;
    underrange_blocks = 0U;
}

void range_control_set_manual(uint8_t range) {
    if (range >= SIGNAL_RANGE_COUNT) {
        return;
    }

    current_mode = RANGE_MODE_MANUAL;
    range_control_set_range(range);
}

RangeMode_t range_control_get_mode(void) {
    return current_mode;
}

const char *range_control_get_range_name(void) {
    static const char *names[SIGNAL_RANGE_COUNT] = {"0.3V", "3.3V", "10V"};
    return (current_range < SIGNAL_RANGE_COUNT) ? names[current_range] : "UNKNOWN";
}

const char *range_control_get_mode_name(void) {
    return (current_mode == RANGE_MODE_AUTO) ? "AUTO" : "MANUAL";
}

uint8_t range_control_update_auto_from_samples(const uint32_t *adc_buf,
                                               uint32_t len) {
    uint16_t min_code = 0x0FFFU;
    uint16_t max_code = 0U;
    uint32_t rail_hits = 0U;

    if (current_mode != RANGE_MODE_AUTO || adc_buf == NULL || len == 0U) {
        return 0U;
    }

    /* Channel A (upper 16 bits) is connected to the ranged AMP_B_OUT path. */
    for (uint32_t i = 0; i < len; i++) {
        uint16_t code = (uint16_t)((adc_buf[i] >> 16) & 0x0FFFU);
        if (code < min_code) min_code = code;
        if (code > max_code) max_code = code;
        if (code <= ADC_RAIL_LOW_CODE || code >= ADC_RAIL_HIGH_CODE) rail_hits++;
    }

    uint32_t rail_limit = (len * ADC_RAIL_HIT_PERCENT + 99U) / 100U;
    if (rail_limit == 0U) rail_limit = 1U;

    uint16_t low_peak = (min_code < ADC_MIDSCALE_CODE)
                      ? (ADC_MIDSCALE_CODE - min_code) : 0U;
    uint16_t high_peak = (max_code > ADC_MIDSCALE_CODE)
                       ? (max_code - ADC_MIDSCALE_CODE) : 0U;
    uint16_t peak_code = (low_peak > high_peak) ? low_peak : high_peak;

    if (rail_hits >= rail_limit) {
        underrange_blocks = 0U;
        if (overrange_blocks < 0xFFU) overrange_blocks++;

        if (overrange_blocks >= AUTO_OVERRANGE_BLOCKS &&
            current_range < SIGNAL_RANGE_10V) {
            range_control_set_range(current_range + 1U);
            return 1U;
        }
        return 0U;
    }

    overrange_blocks = 0U;

    uint8_t is_underrange =
        (current_range == SIGNAL_RANGE_10V && peak_code < ADC_10V_TO_3V3_PEAK) ||
        (current_range == SIGNAL_RANGE_3V3 && peak_code < ADC_3V3_TO_0V3_PEAK);

    if (is_underrange) {
        if (underrange_blocks < 0xFFU) underrange_blocks++;
        if (underrange_blocks >= AUTO_UNDERRANGE_BLOCKS) {
            range_control_set_range(current_range - 1U);
            return 1U;
        }
    } else {
        underrange_blocks = 0U;
    }

    return 0U;
}
