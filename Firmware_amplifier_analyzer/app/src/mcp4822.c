#include "mcp4822.h"
#include "calibration.h"

#if defined(STM32F103xB)
#include "stm32f1xx_hal.h"
#elif defined(STM32F407xx)
#include "stm32f4xx_hal.h"
#endif

extern SPI_HandleTypeDef hspi1;

void mcp4822_init(void) {
    // SPI1 initialization is handled in main.c, but we ensure CS pin is high
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET);
}

uint16_t mcp4822_build_frame(uint8_t channel, uint8_t gain_x2, uint16_t code) {
    // Bit 15: Select channel (0 = A, 1 = B)
    // Bit 14: Reserved (0)
    // Bit 13: Gain (0 = 2x, 1 = 1x)
    // Bit 12: Shutdown (1 = active, 0 = shutdown)
    // Bit 11-0: Data (12-bit)
    uint16_t frame = 0;
    
    if (channel == 1) { // Channel B
        frame |= (1 << 15);
    } // else Channel A (0 << 15)
    
    if (gain_x2 == 0) { // Gain 1x (GA = 1)
        frame |= (1 << 13);
    } // else Gain 2x (GA = 0)
    
    frame |= (1 << 12); // Active
    
    frame |= (code & 0x0FFF);
    
    return frame;
}

void mcp4822_write_raw(uint8_t channel, uint8_t gain_x2, uint16_t code) {
    uint16_t frame = mcp4822_build_frame(channel, gain_x2, code);
    uint8_t data[2];
    data[0] = (uint8_t)((frame >> 8) & 0xFF);
    data[1] = (uint8_t)(frame & 0xFF);
    
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_RESET);
    HAL_SPI_Transmit(&hspi1, data, 2, 100);
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET);
}

void mcp4822_set_voltage_mv(uint8_t channel, uint8_t gain_x2, float voltage_mv) {
    uint16_t code = calibration_voltage_to_dac_code(voltage_mv, gain_x2 ? 2 : 1);
    mcp4822_write_raw(channel, gain_x2, code);
}
