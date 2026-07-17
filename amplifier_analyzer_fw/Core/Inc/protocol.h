#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

#define PKT_HEADER1 0xAA
#define PKT_HEADER2 0xBB

typedef enum {
    FRAME_TYPE_OSC_STREAM  = 0x01,
    FRAME_TYPE_BODE        = 0x02,
    FRAME_TYPE_OSC_CAPTURE = 0x03
} FrameType_t;

#pragma pack(push, 1)
typedef struct {
    uint8_t  header1;
    uint8_t  header2;
    uint8_t  type;
    uint16_t length; // Big Endian
} ProtocolHeader_t;
#pragma pack(pop)

uint8_t protocol_calculate_crc(uint8_t *data, uint16_t len);

// Khai báo hàm gửi dữ liệu (sẽ được định nghĩa trong protocol.c)
void protocol_send_osc_data(uint8_t *data, uint16_t samples);
void protocol_send_raw(uint8_t *data, uint16_t len);
uint8_t protocol_send_raw_async(uint8_t *data, uint16_t len);

#endif
