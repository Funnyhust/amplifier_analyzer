# Nhật ký debug ADC, DAC, USB CDC và ứng dụng desktop

**Dự án:** Amplifier Analyzer – STM32F103C8T6, MCP4822, ADS7861, USB CDC
**Ngày tổng hợp:** 16/07/2026
**Mục đích:** Lưu lại toàn bộ chuỗi lỗi, các giả thuyết đã loại trừ, bằng chứng thực nghiệm và trạng thái hiện tại để không lặp lại quá trình debug.

## 1. Kiến trúc và luồng hoạt động mong muốn

Hệ thống gồm:

- STM32F103C8T6 điều khiển MCP4822 qua SPI1 để phát tín hiệu.
- STM32 đọc đồng thời hai kênh ADS7861 qua giao tiếp serial kiểu SPI trên SPI2.
- PC giao tiếp với STM32 qua USB CDC/COM ảo.
- Ứng dụng desktop gửi `CONFIG`, `START`, `GET_RESULT`, `GET_SAMPLES`, `STOP` và hiển thị waveform cùng các thông số phân tích.

Luồng production mong muốn:

1. App gửi cấu hình tín hiệu và cấu hình capture.
2. STM32 phát DAC liên tục theo sample clock xác định.
3. ADS7861 lấy mẫu hai kênh theo nhịp xác định và ghi vào buffer.
4. USB CDC vẫn phản hồi lệnh trong lúc DAC/ADC hoạt động.
5. App nhận đủ frame, kiểm tra CRC, phân tích và hiển thị mà không treo UI.

## 2. Giai đoạn lỗi ADC và protocol làm ứng dụng báo lỗi

### 2.1. Triệu chứng ban đầu

Ứng dụng từng liên tục báo:

```text
Result parse err: Expecting value: line 1 column 12 (char 11)
```

Sau đó xuất hiện các lỗi rõ hơn khi nhấn bắt đầu đo:

```text
Thiết bị không xác nhận lệnh START.
ERR:204,ADC_FRAME
ERR:204,ADC_FRAME,W0=0000,W1=0000
```

Có lúc `CONFIG` cũng bị app báo thất bại. Điều này cho thấy lỗi không chỉ nằm ở phần vẽ waveform; firmware chưa tạo được capture ADC hợp lệ nên không hoàn thành đúng protocol mà app mong đợi.

### 2.2. Những điểm phần cứng và protocol đã xác định

- ADS7861 dùng tín hiệu **SERIAL DATA A**, ký hiệu SDA trong datasheet. Đây là serial data output của ADC, không phải bus I2C SDA.
- Schematic chỉ nối SERIAL DATA A vào STM32; SERIAL DATA B không được sử dụng.
- Vì vậy chế độ ưu tiên là `M0=0`, `M1=1`, để hai word A/B cùng đi lần lượt qua SERIAL DATA A.
- Mỗi word dài 16 bit; cần tổng cộng 32 clock để đọc hai ADC qua một đường data.
- RD và CONVST dùng chung một net trên bo mạch.
- Dữ liệu ADC là số bù hai 12 bit nằm trong bit `[13:2]`, kèm hai status bit ở đầu word.

### 2.3. Các thay đổi bring-up đã thực hiện cho ADS7861

Driver ADS7861 đã được tách thành thư viện và bổ sung:

- Parse word 16 bit và sign extension dữ liệu 12 bit.
- Chọn cặp A0/B0 hoặc A1/B1.
- Timeout để tránh chờ BUSY vô hạn.
- Chế độ đọc hai word qua SERIAL DATA A.
- Self-test cho các giá trị `0`, `+2047`, `-2048`, `-1`.
- Lưu word ADC cuối để đưa vào thông báo `ADC_FRAME` phục vụ debug.

Trạng thái bring-up hiện tại trong `ads7861.h`:

```c
ADS7861_USE_BUSY_PIN           = 0
ADS7861_USE_BITBANG_BRINGUP    = 1
ADS7861_RELAX_FRAME_VALIDATION = 1
```

Ý nghĩa:

- Chưa tin cậy BUSY nên tạm không dùng BUSY để quyết định hoàn thành conversion.
- SCK của ADS đang được bit-bang chậm để quan sát và giảm số biến khi bring-up.
- Kiểm tra framing đang được nới lỏng để chấp nhận dữ liệu không bị stuck trong giai đoạn xác minh timing.

Đây là cấu hình debug, **chưa phải cấu hình production cuối cùng**.

### 2.4. Kết quả protocol đã từng đạt được

Với cấu hình thử nghiệm 20 kHz, 200 kSPS, 128 mẫu, đã có lần kiểm tra trực tiếp COM4 thành công:

- `CONFIG` trả `OK`.
- `START` trả `OK` sau khoảng 70 ms.
- `GET_RESULT` trả response hợp lệ.
- `GET_SAMPLES` trả đủ 128 cặp mẫu, payload 512 byte.
- CRC frame đúng.
- `STOP` trả `OK`.

Kết quả này chứng minh USB CDC và cấu trúc protocol có thể chạy end-to-end. Tuy nhiên nó chưa chứng minh timing ADS, framing ADS và sample rate thực tế đã đúng.

### 2.5. Lỗi crash của ứng dụng desktop

Trong quá trình đọc liên tục, ứng dụng desktop từng bị crash do vòng đời `QThread`/worker:

- Worker cũ có thể kết thúc sau khi biến worker đã trỏ sang đối tượng mới.
- Đóng cửa sổ hoặc mất COM khi worker đang đọc có thể làm thread bị hủy không an toàn.

Đã sửa theo hướng:

- Callback xác định đúng worker gửi signal bằng `sender()`.
- Không thay worker mới trước khi worker cũ được dọn xong.
- Khi đóng app, chờ worker kết thúc trong thời hạn trước khi đóng serial.
- Serial read chạy ở worker, không block UI thread.

Một lần test headless với COM4 đã chạy 39 capture liên tiếp, nhận frame 518 byte và thoát với mã 0.

## 3. Giai đoạn waveform không giống sine và điều tra DAC

### 3.1. Hiện tượng quan sát trên app

Waveform trên app gần như nằm ngang quanh 250 mV và chỉ có các gai nhỏ. Từ đồ thị app lúc đó chưa thể kết luận:

- DAC không phát đúng;
- ADC đọc sai;
- scale/calibration ADC sai;
- hoặc app chỉ đang hiển thị một frame không hợp lệ.

### 3.2. Quan sát trực tiếp bằng oscilloscope

Khi đo VOUTA của MCP4822 bằng oscilloscope trong firmware production cũ, chỉ thấy một burst/xung ngắn rồi mất tín hiệu. Điều này chuyển hướng điều tra sang luồng điều khiển DAC.

Đọc code production cho thấy nguyên nhân kiến trúc:

- `START` chạy một vòng `for` hữu hạn đúng bằng `current_config.samples`.
- DAC chỉ được ghi trong vòng capture đó.
- Hết vòng lặp, `test_controller_start()` trả về và main production không tiếp tục cập nhật DAC.
- Các lần ghi DAC trong capture không được pacing chính xác theo `Fs`; tốc độ phụ thuộc SPI, ADS và code blocking.
- Khi app gửi `STOP`, firmware gọi shutdown hai kênh MCP4822.

Vì vậy oscilloscope thấy một burst ngắn là đúng với hành vi code cũ; chưa phải bằng chứng chip MCP4822 hỏng.

## 4. Firmware kiểm thử riêng MCP4822 và kết luận về DAC

Một environment riêng đã được thêm:

```ini
[env:mcp4822_test]
```

Firmware này:

- Không khởi tạo hoặc đọc ADS7861.
- Phát sine 50 Hz liên tục trên MCP4822 channel A.
- Dùng 20 điểm mỗi chu kỳ, update rate 1 kHz.
- Gain x2.
- Code DAC từ 1350 đến 1950, tương ứng lý tưởng khoảng 1,35–1,95 V.
- PA3/LDAC giữ LOW.
- Có bộ đếm frame SPI và lệnh `DAC_TEST_STATUS`.

Kết quả đọc COM4:

```text
TX_OK=13871, TX_ERR=0
TX_OK=14874, TX_ERR=0
TX_OK=15876, TX_ERR=0
TX_OK=16880, TX_ERR=0
```

Bộ đếm tăng khoảng 1000 frame mỗi giây, đúng với update rate 1 kHz. `TX_ERR` luôn bằng 0 và `LAST_FRAME` thay đổi theo LUT sine.

Quan trọng hơn, đo trực tiếp bằng oscilloscope xác nhận firmware MCP-only tạo được sine đẹp và liên tục.

### Kết luận đã xác nhận về DAC

- MCP4822 hoạt động.
- Nguồn, VOUTA và đường mạch cơ bản hoạt động.
- SPI1 SCK/MOSI/CS hoạt động.
- PA3/LDAC hoạt động ở cấu hình đang dùng.
- Format frame channel A, gain x2 và LUT sine đúng.
- Lỗi burst ngắn trong production cũ là lỗi luồng firmware, không phải chip DAC.

Do MCP4822 không có đường ACK/MISO, bộ đếm HAL riêng lẻ chỉ chứng minh MCU truyền; bằng chứng oscilloscope là phần xác nhận vật lý quan trọng nhất.

## 5. Đưa bộ phát liên tục về production và lỗi hiện tại

### 5.1. Thay đổi đã đưa vào production

Để DAC tiếp tục chạy sau khi `START` trả về, đã thử kiến trúc:

- TIM3 tạo sample tick.
- SPI1 tăng lên 18 MHz (`PCLK2/4`) để một frame 16 bit mất dưới 1 µs.
- ISR TIM3 gửi từng code LUT bằng đường register-level thay vì `HAL_SPI_Transmit()`.
- USB được đặt ưu tiên cao hơn TIM3.
- `STOP` dừng TIM3 rồi shutdown MCP4822.
- `DAC_TEST_STATUS` báo `TX_OK`, `TX_ERR`, frame cuối, frequency, update rate và trạng thái `RUN`.

Ban đầu timer được bật song song trong lúc capture ADS. Cách này làm `START`/COM timeout nên đã đổi thành:

1. Giữ capture blocking như nhánh bring-up cũ.
2. Chỉ bật stream TIM3 sau khi capture hoàn thành.
3. Sau đó DAC tiếp tục chạy cho tới `STOP`.

### 5.2. Bằng chứng hiện tại

- Firmware production build và nạp thành công.
- Sau khi chạy, oscilloscope hiện cho sine đẹp và liên tục.
- Điều này xác nhận luồng timer + SPI1 + MCP4822 hiện đã tạo được waveform.
- Tuy nhiên lệnh `START` từ script debug có lúc không nhận được response trong 10 giây và sau đó COM4 không mở lại được cho tới khi MCU được reset/nạp lại.
- Khi dừng CPU bằng J-Link trong trạng thái đó, PC nằm trong `mcp4822_write_raw_isr()` và TIM3 đang active. Đây là dấu hiệu cần kiểm tra tải ISR/khả năng USB bị ảnh hưởng, nhưng chưa đủ để kết luận ISR là nguyên nhân duy nhất.

### 5.3. Kết luận hiện tại

Phần DAC không còn là nghi phạm chính vì waveform vật lý đã đẹp và liên tục. Lỗi còn lại nằm trong vùng giao nhau giữa:

- ADS7861 bit-bang/blocking;
- TIM3 DAC interrupt;
- USB CDC command/response;
- thời gian CPU và ưu tiên ngắt;
- cách `START` vừa capture vừa phải phản hồi protocol.

Chưa được phép kết luận ADC hỏng hoặc USB phần cứng hỏng. USB đã từng chạy end-to-end và vẫn enumerate COM4 sau reset. Vấn đề có tính chất runtime khi bắt đầu phép đo.

## 6. Trạng thái code và những điều không nên thay đổi vội

### Phần đã xác nhận tốt

- Frame MCP4822 và driver cơ bản.
- Sine LUT.
- Kết nối SPI1/LDAC/CS đến MCP4822.
- USB CDC enumeration.
- Protocol cơ bản `PING/INFO/CONFIG/START/GET_RESULT/GET_SAMPLES/STOP` trong ít nhất một cấu hình bring-up.
- Parser binary và CRC phía app.
- Vòng đời worker serial của app sau bản sửa.

### Phần đang ở trạng thái bring-up

- BUSY ADS7861 chưa được xác minh bằng logic analyzer.
- CPOL/CPHA và cạnh lấy data ADS cần xác minh lại trên tín hiệu thật.
- Thứ tự word A/B qua SERIAL DATA A cần xác minh.
- Framing ADC hiện đang relax.
- SPI2 hiện bị thay bằng GPIO bit-bang.
- Sample rate ADC thực tế chưa được chứng minh bằng phép đo timing.
- DAC timer ISR và USB CDC chưa được chứng minh chạy ổn định đồng thời ở 200 kSPS.
- Capture mới chưa được tạo liên tục cho mỗi lần app yêu cầu; app có thể đang đọc lại buffer gần nhất.

### Nguyên tắc cho lần debug tiếp theo

- Giữ nguyên nhánh MCP-only và waveform sine hiện tại làm golden reference.
- Không thay đồng thời driver DAC, driver ADC và USB.
- Không dùng waveform app để kết luận DAC khi chưa so sánh oscilloscope tại VOUTA.
- Không đánh dấu `PASS` cho phép đo khi framing ADS hoặc sample rate chưa được xác minh.

## 7. Kế hoạch debug tiếp theo đề xuất

### Bước 1: Đóng băng DAC đã hoạt động

- Không sửa LUT, frame MCP4822, pin mapping hoặc gain bit.
- Đo và ghi lại VOUTA, CS, SCK, MOSI, LDAC ở cấu hình chuẩn.
- Đo CPU/ISR timing bằng một GPIO debug nếu cần.

### Bước 2: Kiểm tra USB khi chỉ chạy DAC

- Chạy DAC ở các update rate 1 kHz, 10 kHz, 50 kHz, 100 kHz, 200 kHz.
- Mỗi mức gửi 100 lần `PING` và đọc `DAC_TEST_STATUS`.
- Xác định ngưỡng bắt đầu mất response.
- Kiểm tra timer ISR có vượt quá chu kỳ sample hay không.

### Bước 3: Kiểm tra ADS độc lập

- Tắt timer DAC nhưng giữ DAC ở một code DC cố định.
- Dùng logic analyzer đo CONVST/RD, BUSY, CLK2, SERIAL DATA A và CS2.
- Xác minh đúng 32 clock, polarity BUSY, cạnh sample và thứ tự word.
- Chỉ bỏ `RELAX_FRAME_VALIDATION` sau khi framing đã đúng.

### Bước 4: Ghép ở tốc độ thấp trước

- Bắt đầu với 50 Hz/1 kSPS hoặc 2 kHz/20 kSPS.
- Xác minh đồng thời: sine liên tục, ADC có dữ liệu, USB trả `PING` và frame đủ CRC.
- Sau đó tăng từng mức thay vì nhảy thẳng lên 200 kSPS.

### Bước 5: Kiến trúc production cuối

Giải pháp dài hạn nên tránh HAL blocking trong ISR và tránh bit-bang ADC khi DAC chạy tốc độ cao. Các hướng cần đánh giá:

- Timer làm timebase chung cho DAC update và CONVST ADC.
- SPI/DMA hoặc state machine interrupt cho DAC và ADC.
- Double buffer/ping-pong buffer cho capture.
- Main loop chỉ xử lý command và buffer hoàn thành.
- USB truyền frame đã hoàn tất, không chờ peripheral trong command handler.

## 8. Tóm tắt kết luận

1. Lỗi app ban đầu xuất phát từ response/capture ADC không hợp lệ và có thêm lỗi quản lý worker serial.
2. Đồ thị gần phẳng trên app không đủ để kết luận DAC hỏng.
3. Production cũ chỉ phát DAC trong một capture hữu hạn nên oscilloscope thấy một burst rồi tắt.
4. Firmware MCP-only và oscilloscope đã xác nhận MCP4822 cùng đường SPI hoạt động tốt.
5. Production hiện có thể tạo sine đẹp, nhưng runtime `START` vẫn có nguy cơ làm USB mất phản hồi.
6. Vùng lỗi còn lại là tích hợp realtime giữa ADS7861, timer DAC và USB CDC; cần debug tách lớp và tăng tốc độ từng bước.
