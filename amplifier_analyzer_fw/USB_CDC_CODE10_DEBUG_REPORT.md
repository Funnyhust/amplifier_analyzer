# Báo cáo debug USB CDC STM32F103 — COM có dấu chấm than, Code 10

## 1. Tóm tắt kết quả

STM32F103 đã xuất hiện trên Windows dưới tên `USB Serial Device (COM3)`, nhưng Device Manager hiển thị dấu chấm than và trạng thái **Code 10 / CM_PROB_FAILED_START**. Ứng dụng Python nhìn thấy tên cổng nhưng không thể mở cổng COM.

Nguyên nhân gốc là bộ cấp phát tĩnh của USB Device chỉ dành **512 byte**, trong khi lớp CDC yêu cầu cấp phát một `USBD_CDC_HandleTypeDef` lớn hơn 512 byte. Vì vậy quá trình đọc descriptor ban đầu vẫn thành công, nhưng lớp CDC thất bại khi Windows gửi lệnh `SET_CONFIGURATION(1)`.

Sau khi sửa bộ cấp phát theo kích thước thực của `USBD_CDC_HandleTypeDef`, thiết bị được Windows khởi động bình thường:

```text
USB Serial Device (COM3)
Status  : OK
Problem : CM_PROB_NONE
```

Kiểm tra giao tiếp thực tế:

```text
TX: PING\n
RX: OK\n
```

## 2. Triệu chứng ban đầu

- Device Manager xuất hiện `USB Serial Device (COM3)`.
- COM3 có biểu tượng tam giác vàng.
- Windows báo thiết bị không thể khởi động, Code 10.
- Driver đang được Windows sử dụng là `usbser.sys` của Microsoft.
- VID/PID nhận đúng là `0483:5740`.
- Rút và cắm lại USB vẫn tạo đúng thiết bị, nên đây không phải bản ghi COM cũ còn sót lại.
- Python/pyserial không thể mở COM3.
- Vi điều khiển vẫn chạy, vẫn kết nối và nạp được qua J-Link/SWD.

Điều này cho thấy phần cứng USB và descriptor chưa hỏng hoàn toàn. Lỗi xảy ra ở một bước sau của quá trình enumeration.

## 3. Quá trình khoanh vùng

### 3.1. Loại trừ lỗi SWD và chip bị khóa

Trước đó firmware từng dùng:

```c
__HAL_AFIO_REMAP_SWJ_DISABLE();
```

Lệnh này tắt cả JTAG và SWD, khiến chip trông giống như bị khóa và chỉ có thể cứu bằng BOOT0. Cấu hình đã được đổi thành:

```c
__HAL_AFIO_REMAP_SWJ_NOJTAG();
```

Cấu hình mới chỉ tắt JTAG để giải phóng chân cần thiết, nhưng vẫn giữ PA13/PA14 cho SWD. Đây là một lỗi riêng, không phải nguyên nhân trực tiếp của Code 10.

### 3.2. Kiểm tra đường đi của USB interrupt

Firmware được bổ sung đúng handler:

```c
void USB_LP_CAN1_RX0_IRQHandler(void)
{
    HAL_PCD_IRQHandler(&hpcd_USB_FS);
}
```

Nếu thiếu handler này, USB có thể bật peripheral nhưng không xử lý được transaction từ host.

### 3.3. Kiểm tra PMA endpoint

Vùng Packet Memory Area được sửa theo bố trí không chồng lấn:

| Endpoint | Chức năng | Địa chỉ PMA |
|---|---|---:|
| EP0 OUT | Control OUT | `0x40` |
| EP0 IN | Control IN | `0x80` |
| EP1 IN | CDC Data IN | `0xC0` |
| EP2 IN | CDC Command IN | `0x100` |
| EP1 OUT | CDC Data OUT | `0x110` |

Bố trí cũ bắt đầu quá thấp và có nguy cơ đè lên vùng Buffer Descriptor Table của USB.

### 3.4. Ghi trace quá trình enumeration qua SWD

Các bộ đếm tạm thời được thêm vào callback USB và đọc trực tiếp qua J-Link. Kết quả:

```text
USB reset count       = 2
USB setup count       = 13
USB data IN count     = 14
USB data OUT count    = 0
CDC Init count        = 0
CDC Control count     = 0
Last setup request    = SET_CONFIGURATION(1)
```

Lịch sử setup cho thấy Windows đã thực hiện được các bước:

1. Lấy Device Descriptor.
2. Gửi `SET_ADDRESS`.
3. Lấy Configuration Descriptor.
4. Lấy String Descriptor.
5. Gửi `SET_CONFIGURATION(1)`.

Như vậy EP0, descriptor, USB clock và interrupt đều hoạt động. Tuy nhiên `CDC_Init_FS()` chưa bao giờ được gọi. Điểm lỗi vì thế nằm trong `USBD_CDC_Init()` trước callback giao diện CDC.

## 4. Nguyên nhân gốc

Trong thư viện STM32 USB Device, `USBD_CDC_Init()` thực hiện cấp phát:

```c
pdev->pClassData = USBD_malloc(sizeof(USBD_CDC_HandleTypeDef));

if (pdev->pClassData == NULL)
{
    ret = 1U;
}
else
{
    ((USBD_CDC_ItfTypeDef *)pdev->pUserData)->Init();
}
```

Allocator cũ của firmware:

```c
static uint8_t usbd_malloc_buffer[512];
static uint32_t usbd_malloc_ptr = 0;
```

Trong khi đó `USBD_CDC_HandleTypeDef` đã chứa riêng:

```c
uint32_t data[CDC_DATA_HS_MAX_PACKET_SIZE / 4U];
```

Với `CDC_DATA_HS_MAX_PACKET_SIZE = 512`, riêng mảng `data` đã chiếm 512 byte. Cấu trúc còn có opcode, độ dài, các con trỏ buffer, độ dài RX/TX và trạng thái RX/TX. Tổng kích thước vì vậy lớn hơn 512 byte.

Kết quả:

```text
USBD_static_malloc(sizeof(USBD_CDC_HandleTypeDef)) -> NULL
USBD_CDC_Init()                                    -> USBD_FAIL
CDC_Init_FS()                                      -> không được gọi
SET_CONFIGURATION                                  -> thất bại
Windows usbser.sys                                 -> Code 10
```

Đây là lý do thiết bị vẫn trả descriptor và xuất hiện tên COM, nhưng Windows không thể khởi động cổng serial.

## 5. Cách sửa chính

Allocator được đổi sang một vùng nhớ tĩnh duy nhất, căn hàng 32 bit và có kích thước tính trực tiếp từ kiểu dữ liệu CDC:

```c
#include "usbd_cdc.h"

static uint32_t usbd_class_memory[
    (sizeof(USBD_CDC_HandleTypeDef) + sizeof(uint32_t) - 1U) /
    sizeof(uint32_t)];

void *USBD_static_malloc(uint32_t size)
{
    if (size > sizeof(usbd_class_memory))
    {
        return NULL;
    }

    return usbd_class_memory;
}

void USBD_static_free(void *p)
{
    (void)p;
}
```

Ưu điểm của cách này:

- Không đoán thủ công kích thước cấu trúc.
- Tự thích ứng nếu thư viện thay đổi cấu trúc CDC.
- Đảm bảo căn hàng 32 bit.
- Không dùng heap động trên STM32F103.
- Phù hợp với đặc điểm lớp CDC chỉ cần một allocation cho class data.

Code hiện tại nằm trong `Core/Src/usbd_conf.c`.

## 6. Các sửa đổi USB liên quan

Ngoài nguyên nhân gốc, các phần sau cũng đã được đưa về cấu hình đúng để hệ thống ổn định.

### 6.1. Chỉ khởi tạo một PCD handle

Loại bỏ khai báo và khởi tạo USB PCD trùng lặp trong `main.c`. USB middleware là nơi duy nhất sở hữu `hpcd_USB_FS` và thực hiện khởi tạo PCD.

### 6.2. Cấu hình chân USB

PA11/PA12 được cấu hình cho USB FS theo cấu hình STM32CubeF1:

```c
GPIO_InitStruct.Pin = GPIO_PIN_11 | GPIO_PIN_12;
GPIO_InitStruct.Mode = GPIO_MODE_AF_INPUT;
GPIO_InitStruct.Pull = GPIO_PULLUP;
GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
```

### 6.3. Ép host nhận biết lần khởi động mới

Firmware kéo PA12 xuống thấp trong khoảng 150 ms trước khi khởi tạo USB, sau đó trả chân về cho USB peripheral. Việc này mô phỏng thao tác disconnect/reconnect, hữu ích với board không có transistor điều khiển pull-up USB.

### 6.4. Hỗ trợ CDC line coding

Firmware lưu và trả lại cấu hình CDC mặc định `115200, 8 data bits, no parity, 1 stop bit`, đồng thời xử lý:

- `CDC_SET_LINE_CODING`
- `CDC_GET_LINE_CODING`

### 6.5. Không xử lý command nặng trong USB ISR

Dữ liệu nhận từ CDC chỉ được đưa vào buffer trong callback USB. Việc parse command và tạo response được chuyển sang vòng lặp chính, tránh giữ interrupt quá lâu.

### 6.6. Chờ hoàn tất USB TX

Các frame phản hồi được gửi tuần tự và chờ trạng thái TX hoàn tất trước khi tái sử dụng buffer, tránh ghi đè dữ liệu khi endpoint vẫn đang truyền.

## 7. Kết quả kiểm tra cuối

Firmware được build và nạp bằng environment:

```powershell
pio run -e usb_cdc_test -t upload
```

Kết quả build cuối:

```text
RAM:   88.7% (18160 / 20480 bytes)
Flash: 62.0% (40640 / 65536 bytes)
Upload protocol: J-Link
Build result: SUCCESS
```

Kiểm tra trạng thái Windows:

```powershell
Get-PnpDevice -PresentOnly |
    Where-Object { $_.InstanceId -like 'USB\VID_0483&PID_5740*' } |
    Format-List Status, FriendlyName, Problem
```

Kết quả:

```text
Status       : OK
FriendlyName : USB Serial Device (COM3)
Problem      : CM_PROB_NONE
```

Kiểm tra bằng Python:

```python
import serial
import time

s = serial.Serial("COM3", 115200, timeout=1, write_timeout=1)
time.sleep(0.15)
s.reset_input_buffer()
s.write(b"PING\n")
s.flush()
print(repr(s.readline()))
s.close()
```

Kết quả:

```text
b'OK\n'
```

## 8. Checklist nếu USB CDC lại xuất hiện Code 10

Kiểm tra theo thứ tự sau:

1. Xác nhận USB clock là 48 MHz.
2. Xác nhận `USB_LP_CAN1_RX0_IRQHandler()` gọi `HAL_PCD_IRQHandler()`.
3. Xác nhận chỉ có một `hpcd_USB_FS` và một lần khởi tạo PCD.
4. Kiểm tra PMA endpoint không chồng Buffer Descriptor Table hoặc chồng nhau.
5. Kiểm tra `USBD_MAX_NUM_INTERFACES` phù hợp với CDC descriptor.
6. Kiểm tra `USBD_RegisterClass()` và `USBD_CDC_RegisterInterface()` đều trả `USBD_OK`.
7. Đặt breakpoint hoặc trace tại `USBD_CDC_Init()` và `CDC_Init_FS()`.
8. Kiểm tra giá trị trả về của `USBD_malloc(sizeof(USBD_CDC_HandleTypeDef))`.
9. Không giả định 512 byte là đủ cho CDC class handle.
10. Sau khi sửa descriptor hoặc VID/PID, rút/cắm lại USB hoặc ép PA12 disconnect để Windows enumerate lại.
11. Kiểm tra Device Manager bằng `Problem`/`ProblemStatus`, không chỉ dựa vào việc tên COM đã xuất hiện.
12. Mở cổng bằng pyserial và thực hiện một lệnh request/response thật.

## 9. Bài học rút ra

- Việc Windows hiển thị tên COM không có nghĩa lớp CDC đã được khởi tạo thành công.
- Nếu host đã gửi được `SET_CONFIGURATION` nhưng callback class chưa chạy, cần kiểm tra phần khởi tạo class, đặc biệt là allocator.
- Buffer có kích thước bằng payload lớn nhất chưa chắc đủ cho cấu trúc quản lý chứa payload đó.
- Trace các USB setup packet qua SWD giúp phân biệt nhanh lỗi descriptor, endpoint, interrupt và class initialization.
- Khi dùng chân JTAG làm GPIO, chỉ nên tắt JTAG bằng `SWJ_NOJTAG`; không dùng `SWJ_DISABLE` nếu vẫn cần nạp/debug qua SWD.

## 10. Tài liệu đối chiếu

- STM32CubeF1, ví dụ CDC standalone chính thức của ST:  
  <https://github.com/STMicroelectronics/STM32CubeF1/tree/master/Projects/STM3210E_EVAL/Applications/USB_Device/CDC_Standalone>
- Phần cấu hình USB low-level của ví dụ:  
  <https://github.com/STMicroelectronics/STM32CubeF1/blob/master/Projects/STM3210E_EVAL/Applications/USB_Device/CDC_Standalone/Src/usbd_conf.c>

