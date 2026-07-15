#include "range_control.h"
#if defined(STM32F103xB)
#include "stm32f1xx_hal.h"
#elif defined(STM32F407xx)
#include "stm32f4xx_hal.h"
#endif

static uint8_t current_range = 0; // 0: direct, 1: div10, 2: div100

void range_control_init(void) {
    range_control_set_range(0);
}

#if defined(STM32F103xB)
#define RANGE_PIN0 GPIO_PIN_8
#define RANGE_PIN1 GPIO_PIN_9
#elif defined(STM32F407xx)
#define RANGE_PIN0 GPIO_PIN_0
#define RANGE_PIN1 GPIO_PIN_1
#endif

void range_control_set_range(uint8_t range) {
    if (range > 2) range = 2;
    current_range = range;
    
    if (range == 0) {
        // Direct
        HAL_GPIO_WritePin(GPIOB, RANGE_PIN0, GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOB, RANGE_PIN1, GPIO_PIN_RESET);
    } else if (range == 1) {
        // Div 10
        HAL_GPIO_WritePin(GPIOB, RANGE_PIN0, GPIO_PIN_SET);
        HAL_GPIO_WritePin(GPIOB, RANGE_PIN1, GPIO_PIN_RESET);
    } else if (range == 2) {
        // Div 100
        HAL_GPIO_WritePin(GPIOB, RANGE_PIN0, GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOB, RANGE_PIN1, GPIO_PIN_SET);
    }
}

uint8_t range_control_get_current_range(void) {
    return current_range;
}

void range_control_update_auto(float vpp_mv) {
    if (current_range == 0) {
        // If Vpp exceeds 3.0V (3000mV), switch to /10 range
        if (vpp_mv > 3000.0f) {
            range_control_set_range(1);
        }
    } else if (current_range == 1) {
        // If Vpp exceeds 30.0V (30000mV), switch to /100 range
        if (vpp_mv > 30000.0f) {
            range_control_set_range(2);
        }
        // If Vpp drops below 2.5V (2500mV), switch back to direct range
        else if (vpp_mv < 2500.0f) {
            range_control_set_range(0);
        }
    } else if (current_range == 2) {
        // If Vpp drops below 25.0V (25000mV), switch back to /10 range
        if (vpp_mv < 25000.0f) {
            range_control_set_range(1);
        }
    }
}
