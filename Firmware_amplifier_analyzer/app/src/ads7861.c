#include "ads7861.h"
#include "calibration.h"

#if defined(STM32F103xB)
#include "stm32f1xx_hal.h"
#elif defined(STM32F407xx)
#include "stm32f4xx_hal.h"
#endif

extern SPI_HandleTypeDef hspi2;

void ads7861_init(void) {
    // Ensure CONVST is low, A0 is low, CS is high
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, GPIO_PIN_RESET); // PB0: CONVST
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_1, GPIO_PIN_RESET); // PB1: A0
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_SET);  // PB12: CS
}

void ads7861_start_conversion(void) {
    // Pulse CONVST high for at least 50 ns (standard CPU delay is enough at 72MHz)
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, GPIO_PIN_SET);
    for (volatile uint32_t i = 0; i < 5; i++);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, GPIO_PIN_RESET);
}

uint16_t ads7861_read_raw(uint8_t channel) {
    if (channel == 1) {
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_1, GPIO_PIN_RESET); // A0 = 0
    } else {
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_1, GPIO_PIN_SET);   // A0 = 1
    }
    
    // Short delay for conversion completion (typically 2-3 us)
    for (volatile uint32_t i = 0; i < 30; i++);
    
    uint8_t rx[2] = {0};
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_RESET);
    HAL_SPI_Receive(&hspi2, rx, 2, 100);
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_SET);
    
    // ADS7861 output is 12-bit, usually right-aligned inside a 16-bit word
    uint16_t raw = ((uint16_t)rx[0] << 8) | rx[1];
    return raw & 0x0FFF;
}

void ads7861_read_pair(uint16_t *ch1, uint16_t *ch2) {
    ads7861_start_conversion();
    *ch1 = ads7861_read_raw(1);
    *ch2 = ads7861_read_raw(2);
}

float ads7861_raw_to_voltage(uint16_t code, uint8_t range) {
    return calibration_adc_code_to_voltage(code, 1, range);
}
