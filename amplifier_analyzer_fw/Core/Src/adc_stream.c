#include "adc_stream.h"
#include "stm32f1xx_hal.h"
#include "protocol.h"
#include <string.h>

#define ADC_STREAM_RING_SIZE 2048U
#define ADC_STREAM_USB_CHUNK 512U
#define ADC_STREAM_MAX_FS_HZ 200000U
#define ADC_STREAM_META_BYTES 10U
#define ADC_STREAM_FRAME_BYTES \
    (5U + ADC_STREAM_META_BYTES + ADC_STREAM_USB_CHUNK * 3U + 1U)

static ads7861_t *stream_dev;
static volatile uint8_t stream_running;
static volatile uint8_t dma_word_state;
static volatile uint8_t dma_rx[4];
static uint8_t dma_dummy;
static volatile uint32_t raw_ring[ADC_STREAM_RING_SIZE]
    __attribute__((aligned(4)));
static volatile uint16_t raw_chunk_sequence[
    ADC_STREAM_RING_SIZE / ADC_STREAM_USB_CHUNK];
static volatile uint32_t ring_write_count;
static volatile uint32_t ring_read_count;
static volatile uint32_t sample_tick_sequence;
static volatile uint32_t active_sample_sequence;
static volatile uint8_t usb_output_enabled;
static volatile uint8_t stream_data_ready;
static uint32_t usb_next_sequence;
static uint8_t usb_sequence_valid;
static uint8_t usb_frames[2][ADC_STREAM_FRAME_BYTES + 4U]
    __attribute__((aligned(4)));
static uint8_t usb_build_index;
static uint8_t usb_pending_valid;
static uint8_t usb_pending_index;
static uint16_t usb_pending_len;
static volatile adc_stream_stats_t stream_stats;

static inline uint8_t *adc_stream_usb_frame(uint8_t index)
{
    /* Keep spare leading bytes so both ping-pong rows retain alignment. */
    return &usb_frames[index][1];
}

static inline void adc_stream_pulse_convst(void)
{
    /* Callers already hold the tied RD/CONVST net LOW. The APB GPIO write
     * plus two core cycles keep HIGH beyond the 15 ns minimum, while avoiding
     * a duplicate BRR write in the critical two-word serial path. */
    stream_dev->convst_port->BSRR = stream_dev->convst_pin;
    __NOP();
    __NOP();
}

static void adc_stream_dma_configure(void)
{
    DMA1_Channel4->CCR &= ~DMA_CCR_EN;
    DMA1_Channel5->CCR &= ~DMA_CCR_EN;
    SPI2->CR2 &= ~(SPI_CR2_RXDMAEN | SPI_CR2_TXDMAEN);
    DMA1->IFCR = DMA_IFCR_CGIF4 | DMA_IFCR_CGIF5;

    dma_dummy = 0U;

    DMA1_Channel4->CPAR = (uint32_t)&SPI2->DR;
    DMA1_Channel4->CMAR = (uint32_t)dma_rx;
    DMA1_Channel4->CCR = DMA_CCR_MINC | DMA_CCR_HTIE |
                         DMA_CCR_PL_1 | DMA_CCR_PL_0;

    DMA1_Channel5->CPAR = (uint32_t)&SPI2->DR;
    DMA1_Channel5->CMAR = (uint32_t)&dma_dummy;
    DMA1_Channel5->CCR = DMA_CCR_DIR | DMA_CCR_PL_1 | DMA_CCR_PL_0;

    __HAL_SPI_ENABLE(stream_dev->hspi);
    SPI2->CR2 |= SPI_CR2_RXDMAEN | SPI_CR2_TXDMAEN;
}

static inline void adc_stream_dma_begin_pair(void)
{
    DMA1_Channel4->CCR &= ~DMA_CCR_EN;
    DMA1_Channel5->CCR &= ~DMA_CCR_EN;
    DMA1->IFCR = DMA_IFCR_CGIF4 | DMA_IFCR_CGIF5;
    DMA1_Channel4->CNDTR = 4U;
    DMA1_Channel5->CNDTR = 2U;
    DMA1_Channel4->CCR |= DMA_CCR_EN;
    DMA1_Channel5->CCR |= DMA_CCR_EN;
}

void adc_stream_init(ads7861_t *dev)
{
    stream_dev = dev;
    stream_running = 0U;
    dma_word_state = 0U;
    ring_write_count = 0U;
    ring_read_count = 0U;
    sample_tick_sequence = 0U;
    usb_output_enabled = 0U;
    stream_data_ready = 0U;
    usb_next_sequence = 0U;
    usb_sequence_valid = 0U;
    usb_build_index = 0U;
    usb_pending_valid = 0U;
    usb_pending_index = 0U;
    usb_pending_len = 0U;
    memset((void *)&stream_stats, 0, sizeof(stream_stats));
}

uint8_t adc_stream_start(uint32_t sample_rate_hz)
{
    ads7861_sample_pair_t sync_sample;
    ads7861_status_t sync_status = ADS7861_ERR_SPI;
    uint32_t timer_clock;
    uint32_t prescaler;
    uint32_t counter_clock;
    uint32_t period_ticks;

    if (stream_dev == NULL || sample_rate_hz == 0U ||
        sample_rate_hz > ADC_STREAM_MAX_FS_HZ) {
        return 0U;
    }

    adc_stream_stop();
    memset((void *)&stream_stats, 0, sizeof(stream_stats));
    ring_write_count = 0U;
    ring_read_count = 0U;
    sample_tick_sequence = 0U;
    stream_data_ready = 0U;
    usb_next_sequence = 0U;
    usb_sequence_valid = 0U;
    usb_build_index = 0U;
    usb_pending_valid = 0U;
    usb_pending_index = 0U;
    usb_pending_len = 0U;
    stream_stats.requested_fs = sample_rate_hz;

    /*
     * STOP may have interrupted the tied RD/CONVST serial transaction between
     * the A and B words.  Complete one blocking pair before arming TIM2 so the
     * ADS7861 pipeline and the STM32 SPI state always start from a verified
     * frame boundary.  This is outside the sampling ISR and only runs once per
     * stream start.
     */
    for (uint8_t attempt = 0U; attempt < 3U; attempt++) {
        sync_status = ads7861_read_pair(stream_dev, ADS7861_PAIR_0,
                                        &sync_sample);
        if (sync_status == ADS7861_OK && sync_sample.valid != 0U) break;
    }
    if (sync_status != ADS7861_OK || sync_sample.valid == 0U) {
        return 0U;
    }

    __HAL_RCC_DMA1_CLK_ENABLE();
    adc_stream_dma_configure();
    /* Sampling timing must not be stretched by USB frame service. */
    HAL_NVIC_SetPriority(DMA1_Channel4_IRQn, 0U, 0U);
    HAL_NVIC_EnableIRQ(DMA1_Channel4_IRQn);

    timer_clock = HAL_RCC_GetPCLK1Freq();
    if ((RCC->CFGR & RCC_CFGR_PPRE1) != RCC_CFGR_PPRE1_DIV1) {
        timer_clock *= 2U;
    }
    prescaler = (timer_clock / sample_rate_hz - 1U) / 65536U;
    if (prescaler > 65535U) return 0U;
    counter_clock = timer_clock / (prescaler + 1U);
    period_ticks = (counter_clock + sample_rate_hz / 2U) / sample_rate_hz;
    if (period_ticks == 0U || period_ticks > 65536U) return 0U;

    __HAL_RCC_TIM2_CLK_ENABLE();
    TIM2->CR1 = 0U;
    TIM2->PSC = (uint16_t)prescaler;
    TIM2->ARR = (uint16_t)(period_ticks - 1U);
    TIM2->CNT = 0U;
    TIM2->EGR = TIM_EGR_UG;
    TIM2->SR = 0U;

    /*
     * When DAC and ADC update at the same rate, sample halfway between two
     * TIM3 DAC writes.  Starting both timers at an arbitrary relative phase
     * made ADS7861 occasionally capture the MCP4822 settling transient even
     * though neither the ADC sequence nor USB frame was lost.
     */
    if ((TIM3->CR1 & TIM_CR1_CEN) != 0U &&
        TIM3->PSC == TIM2->PSC && TIM3->ARR == TIM2->ARR) {
        uint32_t period = period_ticks;
        uint32_t dac_phase = TIM3->CNT % period;
        uint32_t half_period = period / 2U;
        TIM2->CNT = (dac_phase + period - half_period) % period;
    }
    HAL_NVIC_SetPriority(TIM2_IRQn, 0U, 0U);
    HAL_NVIC_EnableIRQ(TIM2_IRQn);

    stream_running = 1U;
    stream_stats.running = 1U;
    TIM2->DIER = TIM_DIER_UIE;
    TIM2->CR1 = TIM_CR1_CEN;
    return 1U;
}

void adc_stream_stop(void)
{
    volatile uint32_t clear;
    uint32_t guard = 1000U;

    TIM2->DIER &= ~TIM_DIER_UIE;
    TIM2->CR1 &= ~TIM_CR1_CEN;
    HAL_NVIC_DisableIRQ(TIM2_IRQn);
    HAL_NVIC_DisableIRQ(DMA1_Channel4_IRQn);
    DMA1_Channel4->CCR &= ~DMA_CCR_EN;
    DMA1_Channel5->CCR &= ~DMA_CCR_EN;
    SPI2->CR2 &= ~(SPI_CR2_RXDMAEN | SPI_CR2_TXDMAEN);
    while ((SPI2->SR & SPI_SR_BSY) != 0U && --guard != 0U) {}
    while ((SPI2->SR & SPI_SR_RXNE) != 0U) {
        clear = *(__IO uint8_t *)&SPI2->DR;
    }
    clear = SPI2->DR;
    clear = SPI2->SR;
    (void)clear;
    DMA1->IFCR = DMA_IFCR_CGIF4 | DMA_IFCR_CGIF5;
    HAL_NVIC_ClearPendingIRQ(DMA1_Channel4_IRQn);
    HAL_NVIC_ClearPendingIRQ(TIM2_IRQn);
    stream_running = 0U;
    usb_output_enabled = 0U;
    usb_pending_valid = 0U;
    dma_word_state = 0U;
    stream_stats.running = 0U;
    if (stream_dev != NULL) {
        stream_dev->cs_port->BSRR = stream_dev->cs_pin;
        stream_dev->convst_port->BRR = stream_dev->convst_pin;
    }
}

static inline void adc_stream_store_pair(uint16_t word_a, uint16_t word_b,
                                         uint32_t sample_sequence)
{
    uint32_t chunk_index;
    uint32_t write_index;

    write_index = ring_write_count & (ADC_STREAM_RING_SIZE - 1U);
    if ((ring_write_count - ring_read_count) >= ADC_STREAM_RING_SIZE) {
        ring_read_count += ADC_STREAM_USB_CHUNK;
        stream_stats.ring_overwrite += ADC_STREAM_USB_CHUNK;
    }
    if ((write_index & (ADC_STREAM_USB_CHUNK - 1U)) == 0U) {
        chunk_index = write_index / ADC_STREAM_USB_CHUNK;
        raw_chunk_sequence[chunk_index] =
            (uint16_t)sample_sequence;
    } else {
        chunk_index = write_index / ADC_STREAM_USB_CHUNK;
    }
    (void)chunk_index;
    raw_ring[write_index] = ((uint32_t)word_a << 16) | word_b;
    ring_write_count++;
    stream_stats.produced++;
    if ((ring_write_count - ring_read_count) >= ADC_STREAM_USB_CHUNK) {
        stream_data_ready = 1U;
    }

}

static inline __attribute__((always_inline)) uint32_t
adc_stream_transport_code(uint32_t raw)
{
    uint16_t word_a = (uint16_t)(raw >> 16);
    uint16_t word_b = (uint16_t)raw;
    uint16_t vin;
    uint16_t vout;

    if ((word_a & 0x4000U) != 0U && (word_b & 0x4000U) == 0U) {
        uint16_t wt = word_a; word_a = word_b; word_b = wt;
    }
    if ((word_a & 0xC003U) != 0x0000U ||
        (word_b & 0xC003U) != 0x4000U) {
        stream_stats.invalid_frame++;
    }
    vin = (uint16_t)(((word_b >> 2) & 0x0FFFU) ^ 0x0800U);
    vout = (uint16_t)(((word_a >> 2) & 0x0FFFU) ^ 0x0800U);
    return ((uint32_t)vin << 12) | (uint32_t)vout;
}

__attribute__((optimize("O3"))) void adc_stream_timer_irq(void)
{
    uint16_t completed_word_a = 0U;
    uint16_t completed_word_b = 0U;
    uint32_t completed_sequence = 0U;
    uint32_t next_sequence;
    uint8_t completed_pair = 0U;

    if ((TIM2->SR & TIM_SR_UIF) == 0U) return;
    TIM2->SR &= ~TIM_SR_UIF;
    if (stream_running == 0U) return;

    next_sequence = sample_tick_sequence++;
    if (dma_word_state != 0U) {
        if (dma_word_state == 2U &&
            (DMA1->ISR & DMA_ISR_TCIF4) != 0U) {
            DMA1->IFCR = DMA_IFCR_CGIF4 | DMA_IFCR_CGIF5;
            DMA1_Channel4->CCR &= ~DMA_CCR_EN;
            DMA1_Channel5->CCR &= ~DMA_CCR_EN;
            completed_word_a = (uint16_t)(
                (((uint16_t)dma_rx[0] << 8) | dma_rx[1]) << 1);
            completed_word_b = (uint16_t)(
                (((uint16_t)dma_rx[2] << 8) | dma_rx[3]) << 1);
            completed_sequence = active_sample_sequence;
            stream_dev->convst_port->BRR = stream_dev->convst_pin;
            stream_dev->cs_port->BSRR = stream_dev->cs_pin;
            dma_word_state = 0U;
            completed_pair = 1U;
        } else {
            stream_stats.timer_overrun++;
            return;
        }
    }

    active_sample_sequence = next_sequence;
    stream_dev->cs_port->BRR = stream_dev->cs_pin;
    adc_stream_pulse_convst();
    dma_word_state = 1U;
    adc_stream_dma_begin_pair();

    /* Parse/store the completed sample while SPI shifts the next word A. */
    if (completed_pair != 0U) {
        adc_stream_store_pair(completed_word_a, completed_word_b,
                              completed_sequence);
    }
}

void adc_stream_dma_irq(void)
{
    if ((DMA1->ISR & DMA_ISR_HTIF4) != 0U && dma_word_state == 1U) {
        /* RX remains armed for all four bytes. Pause SCK after word A by
         * rearming only the two-byte TX DMA, then expose word B. */
        DMA1->IFCR = DMA_IFCR_CHTIF4 | DMA_IFCR_CGIF5;
        DMA1_Channel5->CCR &= ~DMA_CCR_EN;
        stream_dev->convst_port->BRR = stream_dev->convst_pin;
        adc_stream_pulse_convst();
        dma_word_state = 2U;
        DMA1_Channel5->CNDTR = 2U;
        DMA1_Channel5->CCR |= DMA_CCR_EN;
        return;
    }
    DMA1->IFCR = DMA_IFCR_CGIF4 | DMA_IFCR_CGIF5;
}

void adc_stream_get_stats(adc_stream_stats_t *stats)
{
    if (stats == NULL) return;
    __disable_irq();
    memcpy(stats, (const void *)&stream_stats, sizeof(*stats));
    __enable_irq();
}

void adc_stream_set_usb_output(uint8_t enabled)
{
    usb_output_enabled = enabled ? 1U : 0U;
}

__attribute__((optimize("O3"))) void adc_stream_usb_service(void)
{
    uint8_t *frame;
    uint32_t first_sequence;
    uint32_t read_start = 0U;
    uint32_t fs;
    uint32_t available;
    uint16_t count = 0U;
    uint16_t payload_len;
    uint16_t pos;

    uint16_t first_sequence_low = 0U;
    uint32_t build_started;
    uint32_t send_started;
    uint32_t elapsed_cycles;
    uint8_t data_crc = 0U;

    if (stream_running == 0U || usb_output_enabled == 0U) return;

    if (usb_pending_valid != 0U) {
        send_started = DWT->CYCCNT;
        if (protocol_send_raw_async(adc_stream_usb_frame(usb_pending_index),
                                    usb_pending_len) == 0U) {
            return;
        }
        elapsed_cycles = DWT->CYCCNT - send_started;
        if (elapsed_cycles > stream_stats.usb_send_cycles_max) {
            stream_stats.usb_send_cycles_max = elapsed_cycles;
        }
        usb_pending_valid = 0U;
        usb_build_index ^= 1U;
    }

    if (stream_data_ready == 0U) return;

    frame = adc_stream_usb_frame(usb_build_index);

    /* Single producer (ADC ISR), single consumer (main). Cortex-M3 accesses
     * aligned 32-bit counters atomically, so a write-count snapshot is enough;
     * globally masking IRQs here steals timing margin from the next sample. */
    available = ring_write_count - ring_read_count;
    if (available >= ADC_STREAM_USB_CHUNK) {
        uint32_t read_index;
        read_start = ring_read_count;
        read_index = read_start & (ADC_STREAM_RING_SIZE - 1U);
        first_sequence_low = raw_chunk_sequence[
            read_index / ADC_STREAM_USB_CHUNK];
        /* Reserve before parsing; the other USB frame buffer may be in flight. */
        ring_read_count += ADC_STREAM_USB_CHUNK;
        count = ADC_STREAM_USB_CHUNK;
    }
    stream_data_ready =
        ((ring_write_count - ring_read_count) >= ADC_STREAM_USB_CHUNK) ? 1U : 0U;
    fs = stream_stats.requested_fs;
    if (count == 0U) return;
    build_started = DWT->CYCCNT;

    if (usb_sequence_valid != 0U) {
        int16_t delta = (int16_t)(first_sequence_low -
                                  (uint16_t)usb_next_sequence);
        first_sequence = (uint32_t)((int32_t)usb_next_sequence + delta);
    } else {
        first_sequence = first_sequence_low;
        usb_sequence_valid = 1U;
    }

    /* Pack two lossless 12-bit channels into three bytes per sample. */
    pos = 15U;
    {
        uint32_t ring_index = read_start & (ADC_STREAM_RING_SIZE - 1U);
        uint32_t xor_words = 0U;
        uint32_t *destination = (uint32_t *)&frame[pos];
        for (uint16_t i = 0U; i < count; i += 4U) {
            uint32_t p0 = adc_stream_transport_code(raw_ring[ring_index + i]);
            uint32_t p1 = adc_stream_transport_code(raw_ring[ring_index + i + 1U]);
            uint32_t p2 = adc_stream_transport_code(raw_ring[ring_index + i + 2U]);
            uint32_t p3 = adc_stream_transport_code(raw_ring[ring_index + i + 3U]);
            uint32_t w0 = (p0 >> 16) | (p0 & 0x00FF00U) |
                          ((p0 & 0xFFU) << 16) | ((p1 >> 16) << 24);
            uint32_t w1 = ((p1 >> 8) & 0xFFU) |
                          ((p1 & 0xFFU) << 8) |
                          ((p2 >> 16) << 16) |
                          (p2 & 0x00FF00U) << 16;
            uint32_t w2 = (p2 & 0xFFU) |
                          ((p3 >> 16) << 8) |
                          (p3 & 0x00FF00U) << 8 |
                          (p3 & 0xFFU) << 24;
            destination[0] = w0;
            destination[1] = w1;
            destination[2] = w2;
            destination += 3;
            xor_words ^= w0 ^ w1 ^ w2;
        }
        data_crc = (uint8_t)xor_words ^ (uint8_t)(xor_words >> 8) ^
                   (uint8_t)(xor_words >> 16) ^ (uint8_t)(xor_words >> 24);
        pos = (uint16_t)(pos + count * 3U);
    }
    if (count == 0U) return;
    usb_next_sequence = first_sequence + count;

    payload_len = (uint16_t)(ADC_STREAM_META_BYTES + count * 3U);
    frame[0] = PKT_HEADER1;
    frame[1] = PKT_HEADER2;
    frame[2] = FRAME_TYPE_OSC_PACKED12;
    frame[3] = (uint8_t)(payload_len >> 8);
    frame[4] = (uint8_t)payload_len;
    frame[5] = (uint8_t)(first_sequence >> 24);
    frame[6] = (uint8_t)(first_sequence >> 16);
    frame[7] = (uint8_t)(first_sequence >> 8);
    frame[8] = (uint8_t)first_sequence;
    frame[9] = (uint8_t)(fs >> 24);
    frame[10] = (uint8_t)(fs >> 16);
    frame[11] = (uint8_t)(fs >> 8);
    frame[12] = (uint8_t)fs;
    frame[13] = (uint8_t)(count >> 8);
    frame[14] = (uint8_t)count;
    for (uint16_t i = 5U; i < 15U; i++) data_crc ^= frame[i];
    frame[pos] = data_crc;
    send_started = DWT->CYCCNT;
    elapsed_cycles = send_started - build_started;
    if (elapsed_cycles > stream_stats.usb_build_cycles_max) {
        stream_stats.usb_build_cycles_max = elapsed_cycles;
    }
    if (protocol_send_raw_async(frame, (uint16_t)(pos + 1U)) != 0U) {
        usb_build_index ^= 1U;
    } else {
        usb_pending_valid = 1U;
        usb_pending_index = usb_build_index;
        usb_pending_len = (uint16_t)(pos + 1U);
    }
    elapsed_cycles = DWT->CYCCNT - send_started;
    if (elapsed_cycles > stream_stats.usb_send_cycles_max) {
        stream_stats.usb_send_cycles_max = elapsed_cycles;
    }
}
