#include "ads7861.h"
#include "calibration.h"

#if defined(STM32F103xB)
#include "stm32f1xx_hal.h"
#elif defined(STM32F407xx)
#include "stm32f4xx_hal.h"
#endif

extern SPI_HandleTypeDef hspi2;

#define ADS7861_M0_PORT          GPIOB
#define ADS7861_M0_PIN           GPIO_PIN_0
#define ADS7861_A0_PORT          GPIOB
#define ADS7861_A0_PIN           GPIO_PIN_1
#define ADS7861_BUSY_PORT        GPIOB
#define ADS7861_BUSY_PIN         GPIO_PIN_10
#define ADS7861_M1_PORT          GPIOB
#define ADS7861_M1_PIN           GPIO_PIN_11
#define ADS7861_CS_PORT          GPIOB
#define ADS7861_CS_PIN           GPIO_PIN_12
#define ADS7861_RD_CONVST_PORT   GPIOA
#define ADS7861_RD_CONVST_PIN    GPIO_PIN_8

#define ADS7861_SPI_TIMEOUT_MS   100U
#define ADS7861_BUSY_TIMEOUT     1000U

static uint16_t ads7861_decode_word(const uint8_t *data) {
    uint16_t word = ((uint16_t)data[0] << 8) | data[1];

    /* Format: channel status (2 bits), ADC data (12 bits), trailing 00. */
    return (word >> 2) & 0x0FFFU;
}

void ads7861_init(void) {
    /* Schematic uses Mode II: M0=0, M1=1, both results on SERIAL DATA A. */
    HAL_GPIO_WritePin(ADS7861_M0_PORT, ADS7861_M0_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(ADS7861_M1_PORT, ADS7861_M1_PIN, GPIO_PIN_SET);

    /* Only Channel A0/B0 are populated on this board. */
    HAL_GPIO_WritePin(ADS7861_A0_PORT, ADS7861_A0_PIN, GPIO_PIN_RESET);

    HAL_GPIO_WritePin(ADS7861_CS_PORT, ADS7861_CS_PIN, GPIO_PIN_SET);
    HAL_GPIO_WritePin(ADS7861_RD_CONVST_PORT, ADS7861_RD_CONVST_PIN,
                      GPIO_PIN_RESET);
}

void ads7861_start_conversion(void) {
    /* RD and CONVST are tied to PA8. A rising pulse starts conversion. */
    HAL_GPIO_WritePin(ADS7861_RD_CONVST_PORT, ADS7861_RD_CONVST_PIN,
                      GPIO_PIN_SET);
    for (volatile uint32_t i = 0; i < 5; i++);
    HAL_GPIO_WritePin(ADS7861_RD_CONVST_PORT, ADS7861_RD_CONVST_PIN,
                      GPIO_PIN_RESET);
}

uint16_t ads7861_read_raw(uint8_t channel) {
    uint16_t channel_a = 0;
    uint16_t channel_b = 0;

    ads7861_read_pair(&channel_a, &channel_b);
    return (channel == 1U) ? channel_a : channel_b;
}

void ads7861_read_pair(uint16_t *ch1, uint16_t *ch2) {
    uint8_t rx[4] = {0};
    uint32_t timeout = ADS7861_BUSY_TIMEOUT;

    if (ch1 == NULL || ch2 == NULL) {
        return;
    }

    *ch1 = 0;
    *ch2 = 0;

    /* M0=0 and A0=0 select the populated Channel A0/B0 input pair. */
    HAL_GPIO_WritePin(ADS7861_A0_PORT, ADS7861_A0_PIN, GPIO_PIN_RESET);

    /*
     * Mode II returns A then B on SDA. Because RD and CONVST are tied, each
     * 16-bit word needs its own synchronization pulse. The second CONVST pulse
     * is intentionally ignored as a new conversion by the ADS7861.
     */
    HAL_GPIO_WritePin(ADS7861_CS_PORT, ADS7861_CS_PIN, GPIO_PIN_RESET);
    ads7861_start_conversion();

    if (HAL_SPI_Receive(&hspi2, &rx[0], 2U, ADS7861_SPI_TIMEOUT_MS) != HAL_OK) {
        HAL_GPIO_WritePin(ADS7861_CS_PORT, ADS7861_CS_PIN, GPIO_PIN_SET);
        return;
    }

    ads7861_start_conversion();
    if (HAL_SPI_Receive(&hspi2, &rx[2], 2U, ADS7861_SPI_TIMEOUT_MS) != HAL_OK) {
        HAL_GPIO_WritePin(ADS7861_CS_PORT, ADS7861_CS_PIN, GPIO_PIN_SET);
        return;
    }

    HAL_GPIO_WritePin(ADS7861_CS_PORT, ADS7861_CS_PIN, GPIO_PIN_SET);

    /* BUSY is high during conversion and should be low after the data clocks. */
    while (HAL_GPIO_ReadPin(ADS7861_BUSY_PORT, ADS7861_BUSY_PIN) == GPIO_PIN_SET) {
        if (timeout-- == 0U) {
            return;
        }
    }

    *ch1 = ads7861_decode_word(&rx[0]);
    *ch2 = ads7861_decode_word(&rx[2]);
}

float ads7861_raw_to_voltage(uint16_t code, uint8_t range) {
    return calibration_adc_code_to_voltage(code, 1, range);
}
