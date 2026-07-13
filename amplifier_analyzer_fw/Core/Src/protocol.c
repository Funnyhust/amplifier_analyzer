#include "protocol.h"
#include "usbd_cdc_if.h"
#include "main.h"

#define PROTOCOL_TX_TIMEOUT_MS 100U

extern USBD_HandleTypeDef hUsbDeviceFS;

static uint8_t protocol_wait_tx_complete(void) {
    USBD_CDC_HandleTypeDef *hcdc =
        (USBD_CDC_HandleTypeDef *)hUsbDeviceFS.pClassData;
    uint32_t started = HAL_GetTick();

    if (hcdc == NULL) {
        return 0U;
    }

    while (hcdc->TxState != 0U) {
        if ((HAL_GetTick() - started) >= PROTOCOL_TX_TIMEOUT_MS) {
            return 0U;
        }
    }

    return 1U;
}

uint8_t protocol_calculate_crc(uint8_t *data, uint16_t len) {
    uint8_t crc = 0;
    for (uint16_t i = 0; i < len; i++) {
        crc ^= data[i];
    }
    return crc;
}

void protocol_send_raw(uint8_t *data, uint16_t len) {
    if (len == 0) return;

    if (!protocol_wait_tx_complete()) {
        return;
    }

    if (CDC_Transmit_FS(data, len) != USBD_OK) {
        return;
    }

    /* The USB stack keeps the caller's buffer until this transfer completes. */
    (void)protocol_wait_tx_complete();
}

void protocol_send_osc_data(uint8_t *data, uint16_t samples) {
    uint16_t payload_len = samples * 4; // 2 channels, each 2 bytes
    
    ProtocolHeader_t header;
    header.header1 = PKT_HEADER1;
    header.header2 = PKT_HEADER2;
    header.type = FRAME_TYPE_OSC_STREAM;
    header.length = (payload_len >> 8) | (payload_len << 8); // Big Endian
    
    // Gửi Header
    protocol_send_raw((uint8_t*)&header, sizeof(ProtocolHeader_t));
    
    // Gửi Dữ liệu
    protocol_send_raw(data, payload_len);
    
    // Gửi Checksum
    uint8_t crc = protocol_calculate_crc(data, payload_len);
    protocol_send_raw(&crc, 1);
}
