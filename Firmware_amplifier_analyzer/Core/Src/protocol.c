#include "protocol.h"
#include "usbd_cdc_if.h"

uint8_t protocol_calculate_crc(uint8_t *data, uint16_t len) {
    uint8_t crc = 0;
    for (uint16_t i = 0; i < len; i++) {
        crc ^= data[i];
    }
    return crc;
}

void protocol_send_osc_data(uint8_t *data, uint16_t samples) {
    uint16_t payload_len = samples * 4; // 2 kênh, mỗi mẫu 2 bytes (uint16)
    
    ProtocolHeader_t header;
    header.header1 = PKT_HEADER1;
    header.header2 = PKT_HEADER2;
    header.type = FRAME_TYPE_OSC_STREAM;
    header.length = (payload_len >> 8) | (payload_len << 8); // Big Endian
    
    // Gửi Header
    CDC_Transmit_FS((uint8_t*)&header, sizeof(ProtocolHeader_t));
    
    // Gửi Dữ liệu
    CDC_Transmit_FS(data, payload_len);
    
    // Gửi Checksum
    uint8_t crc = protocol_calculate_crc(data, payload_len);
    CDC_Transmit_FS(&crc, 1);
}
