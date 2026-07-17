#include "mcp4822.h"
#include "calibration.h"

#if defined(STM32F103xB)
#include "stm32f1xx_hal.h"
#elif defined(STM32F407xx)
#include "stm32f4xx_hal.h"
#endif

extern SPI_HandleTypeDef hspi1;

#define MCP4822_LDAC_PORT GPIOA
#define MCP4822_LDAC_PIN  GPIO_PIN_3
#define MCP4822_CS_PORT   GPIOA
#define MCP4822_CS_PIN    GPIO_PIN_4

static volatile uint32_t mcp4822_tx_ok_count = 0U;
static volatile uint32_t mcp4822_tx_error_count = 0U;
static volatile uint16_t mcp4822_last_frame = 0U;
static volatile uint8_t mcp4822_isr_inflight = 0U;

#define MCP4822_FRAME(channel, gain_x2, active, code)                 \
    ((uint16_t)((((channel) == MCP4822_CHANNEL_B) ? 0x8000U : 0U) | \
                (((gain_x2) == MCP4822_GAIN_X1) ? 0x2000U : 0U) |   \
                ((active) ? 0x1000U : 0U) | ((code) & 0x0FFFU)))

_Static_assert(MCP4822_FRAME(MCP4822_CHANNEL_A, MCP4822_GAIN_X2, 1U,
                             0x0ABCU) == 0x1ABCU,
               "MCP4822 channel A X2 frame is invalid");
_Static_assert(MCP4822_FRAME(MCP4822_CHANNEL_A, MCP4822_GAIN_X1, 1U,
                             0x0ABCU) == 0x3ABCU,
               "MCP4822 channel A X1 frame is invalid");
_Static_assert(MCP4822_FRAME(MCP4822_CHANNEL_B, MCP4822_GAIN_X2, 1U,
                             0x0ABCU) == 0x9ABCU,
               "MCP4822 channel B X2 frame is invalid");
_Static_assert(MCP4822_FRAME(MCP4822_CHANNEL_B, MCP4822_GAIN_X1, 1U,
                             0x0ABCU) == 0xBABCU,
               "MCP4822 channel B X1 frame is invalid");

static uint16_t mcp4822_build_frame_mode(uint8_t channel, uint8_t gain_x2,
                                         uint8_t active, uint16_t code) {
    return MCP4822_FRAME(channel, gain_x2, active, code);
}

static MCP4822_Status_t mcp4822_transmit_frame(uint16_t frame) {
    MCP4822_CS_PORT->BRR = MCP4822_CS_PIN;
    HAL_StatusTypeDef hal_status = HAL_SPI_Transmit(
        &hspi1, (uint8_t *)&frame, 1U, 100U);
    MCP4822_CS_PORT->BSRR = MCP4822_CS_PIN;

    mcp4822_last_frame = frame;
    if (hal_status == HAL_OK) {
        mcp4822_tx_ok_count++;
    } else {
        mcp4822_tx_error_count++;
    }

    return (hal_status == HAL_OK) ? MCP4822_OK : MCP4822_ERROR;
}

void mcp4822_init(void) {
    /*
     * LDAC is active-low. The board connects it to PA3 and production mode
     * keeps it low, therefore each completed SPI frame updates the output
     * when CS returns high. CS is inactive-high.
     */
    HAL_GPIO_WritePin(MCP4822_LDAC_PORT, MCP4822_LDAC_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(MCP4822_CS_PORT, MCP4822_CS_PIN, GPIO_PIN_SET);
    mcp4822_tx_ok_count = 0U;
    mcp4822_tx_error_count = 0U;
    mcp4822_last_frame = 0U;
    mcp4822_isr_inflight = 0U;
}

uint16_t mcp4822_build_frame(uint8_t channel, uint8_t gain_x2, uint16_t code) {
    return mcp4822_build_frame_mode(channel, gain_x2, 1U, code);
}

MCP4822_Status_t mcp4822_write_raw(uint8_t channel, uint8_t gain_x2,
                                    uint16_t code) {
    return mcp4822_transmit_frame(
        mcp4822_build_frame(channel, gain_x2, code)
    );
}

MCP4822_Status_t mcp4822_write_raw_isr(uint8_t channel, uint8_t gain_x2,
                                        uint16_t code) {
#if defined(STM32F103xB)
    const uint16_t frame = mcp4822_build_frame(channel, gain_x2, code);
    volatile uint16_t discard;

    /*
     * The production sample timer can run at 200 kHz, so HAL_SPI_Transmit()
     * is too expensive inside the ISR. SPI1 belongs exclusively to MCP4822;
     * Complete the previous frame, then launch this 16-bit frame and return.
     * SPI shifts in hardware while CS stays low until the next DAC tick.
     */
    if (mcp4822_isr_inflight != 0U) {
        if ((SPI1->SR & SPI_SR_BSY) != 0U ||
            (SPI1->SR & SPI_SR_RXNE) == 0U) goto spi_error;
        discard = (uint16_t)SPI1->DR;
        (void)discard;
        MCP4822_CS_PORT->BSRR = MCP4822_CS_PIN;
        mcp4822_tx_ok_count++;
        mcp4822_isr_inflight = 0U;
        __NOP();
        __NOP();
    }
    if ((SPI1->SR & SPI_SR_TXE) == 0U) goto spi_error;
    MCP4822_CS_PORT->BRR = MCP4822_CS_PIN;
    SPI1->DR = frame;
    mcp4822_isr_inflight = 1U;
    mcp4822_last_frame = frame;
    return MCP4822_OK;

spi_error:
    MCP4822_CS_PORT->BSRR = MCP4822_CS_PIN;
    mcp4822_isr_inflight = 0U;
    mcp4822_last_frame = frame;
    mcp4822_tx_error_count++;
    return MCP4822_ERROR;
#else
    return mcp4822_write_raw(channel, gain_x2, code);
#endif
}

void mcp4822_flush_isr(void) {
#if defined(STM32F103xB)
    volatile uint32_t guard = 1000U;
    volatile uint16_t discard;

    if (mcp4822_isr_inflight == 0U) return;
    while ((SPI1->SR & SPI_SR_BSY) != 0U && --guard != 0U) {}
    if (guard != 0U && (SPI1->SR & SPI_SR_RXNE) != 0U) {
        discard = (uint16_t)SPI1->DR;
        (void)discard;
        mcp4822_tx_ok_count++;
    } else {
        mcp4822_tx_error_count++;
    }
    MCP4822_CS_PORT->BSRR = MCP4822_CS_PIN;
    mcp4822_isr_inflight = 0U;
#endif
}

void mcp4822_account_dma_cycle(uint32_t frames, uint16_t last_frame) {
    mcp4822_tx_ok_count += frames;
    mcp4822_last_frame = last_frame;
}

void mcp4822_account_dma_error(void) {
    mcp4822_tx_error_count++;
}

MCP4822_Status_t mcp4822_set_voltage_mv(uint8_t channel, uint8_t gain_x2,
                                        float voltage_mv) {
    uint16_t code = calibration_voltage_to_dac_code(voltage_mv, gain_x2 ? 2 : 1);
    return mcp4822_write_raw(channel, gain_x2, code);
}

MCP4822_Status_t mcp4822_shutdown(uint8_t channel, uint8_t gain_x2) {
    return mcp4822_transmit_frame(
        mcp4822_build_frame_mode(channel, gain_x2, 0U, 0U)
    );
}

MCP4822_Status_t mcp4822_write_both_sync(uint8_t gain_a_x2,
                                         uint16_t code_a,
                                         uint8_t gain_b_x2,
                                         uint16_t code_b) {
    MCP4822_Status_t status;

    /* Hold both output latches while filling the channel input registers. */
    HAL_GPIO_WritePin(MCP4822_LDAC_PORT, MCP4822_LDAC_PIN, GPIO_PIN_SET);
    status = mcp4822_write_raw(MCP4822_CHANNEL_A, gain_a_x2, code_a);
    if (status == MCP4822_OK) {
        status = mcp4822_write_raw(MCP4822_CHANNEL_B, gain_b_x2, code_b);
    }

    /* One active-low edge applies both values; leave LDAC low for fast writes. */
    HAL_GPIO_WritePin(MCP4822_LDAC_PORT, MCP4822_LDAC_PIN, GPIO_PIN_RESET);
    __NOP();
    __NOP();
    return status;
}

uint32_t mcp4822_get_tx_ok_count(void) {
    return mcp4822_tx_ok_count;
}

uint32_t mcp4822_get_tx_error_count(void) {
    return mcp4822_tx_error_count;
}

uint16_t mcp4822_get_last_frame(void) {
    return mcp4822_last_frame;
}
