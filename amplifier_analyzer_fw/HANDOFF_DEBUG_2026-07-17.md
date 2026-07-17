# Bàn giao debug ADC, DAC và USB CDC

**Ngày cập nhật:** 17/07/2026  
**Workspace:** `D:\hust\amplifier_analyzer\amplifier_analyzer`  
**Firmware:** `amplifier_analyzer_fw`  
**Cổng thiết bị gần nhất:** `COM4`  
**Trạng thái kết luận:** DAC đã hoạt động; ADS7861 chưa đọc đúng framing; chưa được coi ADC là hoàn thành.

## 1. Mục tiêu đang thực hiện

Giữ MCP4822 phát sine liên tục trong khi debug ADS7861, để có tín hiệu thật đi vào ADC và có thể đo đồng thời bằng oscilloscope. Firmware cần đồng thời:

- Phát sine liên tục qua MCP4822.
- Đọc hai kênh ADS7861 cùng thời điểm.
- Vẫn trả lời lệnh USB CDC ổn định.
- Sau khi ADC đúng mới ghép lại với ứng dụng desktop và tối ưu tốc độ.

Ưu tiên hiện tại là **chạy đúng ở tốc độ thấp/bring-up trước**, chưa tối ưu 200 kSPS cho ADC.

## 2. Phần cứng và ánh xạ tín hiệu

### MCP4822

- SPI1.
- `PA3` nối `LDAC`.
- DAC đã được xác nhận bằng oscilloscope là phát sine đẹp, liên tục.
- Firmware production cũ chỉ phát trong vòng capture hữu hạn, nên trước đây chỉ thấy một burst rồi mất. Đây là lỗi luồng firmware, không phải bằng chứng MCP4822 hỏng.

### ADS7861

| Tín hiệu ADS7861 | STM32 | Ghi chú |
|---|---|---|
| BUSY | PB10 | GPIO input |
| CLK | PB13 | SPI2 SCK hoặc bit-bang khi bring-up |
| CS | PB12 | Active LOW |
| SERIAL DATA A | PB14 | MISO2; datasheet gọi là SDA, không phải I2C |
| RD/CONVST | PA8 | Hai chân ADC nối chung trên schematic |
| M0 | PB0 | Mode select |
| A0 | PB1 | Chọn pair 0/1 |
| M1 | PB11 | Mode select |

Schematic chỉ nối **SERIAL DATA A** về MCU, không nối SERIAL DATA B. Mode bring-up dự kiến:

```text
M0 = 0
M1 = 1
A0 = 0: đọc A0/B0
```

Đường analog thực tế:

- `CHA0+` (tín hiệu DAC phát) đi vào **CHB0+** của ADS7861; CHB0− được bias 2.5 V. Đây là Vin.
- `AMP_B_OUT` (đầu ra DUT) đi vào **CHA0+** của ADS7861; CHA0− được bias 1.65 V. Đây là Vout.
- Vì vậy mapping đúng về sau phải là **ADS B0 → CH1/Vin**, **ADS A0 → CH2/Vout**.
- Code hiện có khả năng vẫn đang gán A→Vin và B→Vout. Chưa sửa mapping này vì framing ADC còn sai; chỉ sửa sau khi đọc word đúng.

## 3. Những phần đã xác nhận hoạt động

### DAC

- MCP4822, nguồn, VOUTA, SPI1, CS và LDAC đều hoạt động.
- Firmware test MCP-only tạo sine liên tục và oscilloscope xác nhận sine đẹp.
- Bộ đếm `DAC_TEST_STATUS` tăng đều, `TX_ERR=0`.
- Production đã được đổi để TIM3 tiếp tục cập nhật DAC sau capture, thay vì chỉ phát một burst.
- Cấu hình debug gần nhất:
  - SINE 20 kHz
  - amplitude 300 mV
  - offset 0 V
  - DAC gain X2
  - update rate 200 kSPS
  - capture 128 mẫu

### USB CDC và protocol

- Thiết bị enumerate thành COM bình thường.
- Đã từng kiểm tra end-to-end thành công `CONFIG`, `START`, `GET_RESULT`, `GET_SAMPLES`, CRC và `STOP` ở bản bring-up.
- USB priority hiện là 1, TIM3 priority là 2.
- SPI1 hiện chạy 18 MHz.
- Khi DAC chạy 200 kSPS, các lệnh debug ADC ngắn vẫn truyền được qua COM.
- Response dài hơn 64 byte từng làm firmware chờ trong `protocol_wait_tx_complete`; vì vậy các lệnh chẩn đoán mới đã được rút ngắn.

### Ứng dụng desktop

- App từng crash do vòng đời worker/QThread; đã có sửa để quản lý worker và đóng serial an toàn hơn.
- Tuy nhiên hiện không nên dùng waveform app để kết luận ADC/DAC cho tới khi framing ADS7861 đúng.
- Phạm vi ưu tiên hiện tại là firmware trước; app chỉ cần dùng sau khi firmware trả raw frame hợp lệ.

## 4. Trạng thái driver ADS7861 hiện tại

Cấu hình bring-up đang dùng:

```c
ADS7861_USE_BUSY_PIN           = 0
ADS7861_USE_BITBANG_BRINGUP    = 1
ADS7861_RELAX_FRAME_VALIDATION = 1
```

Ý nghĩa:

- Chưa dùng BUSY làm điều kiện chính vì sequence/polarity chưa được xác minh chắc chắn.
- CLK đang bit-bang để giảm tốc độ và dễ cô lập timing.
- Validation đang nới lỏng, nên `valid` hiện không có nghĩa framing đã đúng.
- Đây không phải cấu hình production cuối.

Các file chính đã thay đổi trong chuỗi debug gần nhất:

- `Core/Inc/ads7861.h`
- `Core/Src/ads7861.c`
- `Core/Src/command_parser.c`

Không động vào các thay đổi không liên quan trong thư mục report.

## 5. Các lệnh chẩn đoán đã thêm

### Đọc một pair

```text
ADC_READ_ONCE
```

Response chứa các trường tương tự:

```text
DATA:ERR=...,W0=...,W1=...,RA=...,RB=...,SA=...,SB=...,VALID=...,STRICT=...,B0=...,B1=...
```

`STRICT` kiểm tra status mong đợi và hai bit cuối word phải bằng 0.

### Ép M1

```text
ADC_FORCE_M1:0
ADC_FORCE_M1:1
```

Mục đích: kiểm tra đường PB11/M1 và ảnh hưởng của mode lên dữ liệu.

### Chọn cạnh lấy mẫu bit-bang

```text
ADC_SAMPLE_EDGE:RISING
ADC_SAMPLE_EDGE:FALLING
```

Cả hai cạnh đã thử; đều chưa sửa được status/framing.

### Đọc ba word liên tiếp

```text
ADC_READ_TRIPLE
ADC_READ_TRIPLE1
```

- `ADC_READ_TRIPLE`: pair 0, A0/B0.
- `ADC_READ_TRIPLE1`: pair 1, A1/B1.
- Response ngắn:

```text
DATA:E=0,W=xxxx,xxxx,xxxx,S=x,x,x
```

`ADC_READ_TRIPLE1` vừa được thêm, đã build và upload thành công nhưng **chưa chạy so sánh pair 0/pair 1 sau lần reset cuối**.

## 6. Kết quả điều tra framing ADS7861

Theo datasheet TI:

- Mode II dùng `M0=0, M1=1`.
- Hai kết quả đi nối tiếp qua SERIAL DATA A.
- Cần 32 clock tổng cộng.
- Mỗi word gồm:
  - bit 15: channel 0/1
  - bit 14: A/B
  - bit 13..2: data signed 12-bit
  - bit 1..0: `00`
- Do RD và CONVST nối chung, cần một cạnh/xung thứ hai ở ranh giới 16 clock để đưa word B ra SERIAL DATA A. Xung này bị bỏ qua về mặt bắt đầu conversion mới nhưng cần cho quá trình đọc mode II.

### Thử bỏ xung RD/CONVST thứ hai

- Kết quả: 12/12 lần word thứ hai trở thành `0000`.
- Kết luận: không được bỏ xung thứ hai trong cấu hình phần cứng RD/CONVST nối chung này.
- Xung đã được khôi phục.

### Sau khi khôi phục xung thứ hai

- 20/20 lần `STRICT=0`.
- Status thường là `SA=0, SB=0`, tức cả hai đều bị nhận là A0 thay vì A0/B0.
- Word điển hình: `3000` và `1FFA`.
- `1FFA` có hai bit cuối không phải `00`, nên rõ ràng word/framing chưa hợp lệ.

### Thử M1 thấp/cao

- `ADC_FORCE_M1:0/1` làm pattern dữ liệu thay đổi, chứng tỏ PB11/M1 có ảnh hưởng đến chip hoặc đường đọc.
- Tuy nhiên status vẫn A/A.
- Driver hiện re-arm M1 LOW→HIGH trước mỗi `ads7861_read_pair()` và trước đọc triplet. Dữ liệu ổn định hơn phần nào nhưng framing vẫn sai.

### Thử cạnh lấy mẫu

- Đã thử lấy bit sau cạnh rising và falling.
- Cả hai đều cho `STRICT=0`, status A/A và word gần giống nhau.
- Cạnh lấy mẫu bit-bang không phải nguyên nhân duy nhất hoặc chính.
- Mặc định hiện đã trả về RISING sau thử nghiệm.

### Đọc ba word pair 0

Các pattern thường gặp:

```text
3000,1FFA,30xx
1FFA,30xx,1FFA
```

Status triplet luôn:

```text
0,0,0
```

Bus có ít nhất hai giá trị khác nhau, nhưng bit status A/B chưa bao giờ thành B. Chưa thể tin dữ liệu raw hay voltage chuyển đổi.

## 7. Trạng thái chính xác tại thời điểm bàn giao

- Binary mới nhất đã build và upload thành công bằng:

```powershell
cd D:\hust\amplifier_analyzer\amplifier_analyzer\amplifier_analyzer_fw
pio run --target upload
```

- Đây là cách upload người dùng xác nhận hoạt động. J-Link đôi lúc báo lỗi DAP nếu dùng cách gọi khác.
- Lần upload cuối đã reset board.
- Vì reset nên DAC hiện có thể đang OFF cho tới khi gửi lại `CONFIG` và `START`.
- Firmware mới nhất có cả `ADC_READ_TRIPLE` và `ADC_READ_TRIPLE1`.
- Chưa chạy test pair 1 sau lần upload cuối.
- Không được tuyên bố ADC đã fix.

## 8. Việc cần làm ngay ở khung chat mới

### Bước 1 — Khởi động lại DAC và để chạy liên tục

1. Đợi board enumerate COM4 sau reset.
2. Dùng Python/pyserial gửi cấu hình debug chuẩn và `START`.
3. Kiểm tra:

```text
DAC_TEST_STATUS
```

Phải thấy `RUN=1`, `TX_OK` tăng và `TX_ERR=0`.

Không gửi `STOP` sau khi test; để DAC chạy cho người dùng đo oscilloscope và để tín hiệu đi vào ADC.

### Bước 2 — So sánh pair 0 và pair 1

Gửi lặp 6–10 lần mỗi lệnh:

```text
ADC_READ_TRIPLE
ADC_READ_TRIPLE1
```

Kỳ vọng status nếu framing đúng:

| Pair | Word A | Word B |
|---|---:|---:|
| Pair 0 | status 0 (A0) | status 1 (B0) |
| Pair 1 | status 2 (A1) | status 3 (B1) |

Nếu pair 1 vẫn trả toàn status `0`, hai status bit đang bị lệch/không được capture đúng. So sánh xem data word pair 1 có đổi đáng kể so với pair 0 không.

### Bước 3 — Khoanh vùng vật lý bằng logic analyzer/oscilloscope

Nếu pair 0/1 đều status 0, cần quan sát đồng thời:

- PA8 RD/CONVST
- PB12 CS
- PB13 CLK
- PB14 SERIAL DATA A
- PB10 BUSY
- PB11 M1
- PB1 A0

Cần xác minh:

- Chính xác 16 clock cho mỗi word, 32 clock mỗi pair.
- Thời điểm xung RD/CONVST thứ hai so với clock thứ 16.
- CS giữ đúng mức trong cả quá trình.
- Bit đầu tiên có bị đọc sớm/muộn một hoặc nhiều clock không.
- M1 thực sự HIGH tại chân chip.
- A0 đổi ở chân chip khi gọi `ADC_READ_TRIPLE1`.
- BUSY có sequence hợp lý sau CONVST.

### Bước 4 — Chỉ sau khi framing đúng

- Tắt `ADS7861_RELAX_FRAME_VALIDATION`.
- Xác nhận raw gần 0 khi differential input bằng 0.
- Xác nhận chiều và độ lớn raw bằng điện áp đã biết.
- Sửa mapping: B0→Vin/CH1, A0→Vout/CH2.
- Sau đó mới ghép app desktop, tăng SPI clock, dùng hardware SPI/DMA và tối ưu sample rate.

## 9. Lưu ý vận hành và tránh lặp lại lỗi

- Dùng `py -3.15` nếu cần chạy script Python; pyserial 3.5 đã có trên máy ở lần kiểm tra trước.
- Phải đóng app desktop trước khi script Python mở COM4.
- Response USB CDC debug nên giữ dưới khoảng 64 byte hoặc truyền theo cơ chế không block.
- Sau upload/reset luôn phải gửi lại CONFIG/START nếu muốn DAC phát.
- Không gửi STOP cuối bài test nếu mục tiêu là để sine chạy liên tục.
- Không kết luận DAC hỏng: oscilloscope đã xác nhận DAC tốt.
- Không tin `VALID=1` khi `ADS7861_RELAX_FRAME_VALIDATION=1`; phải xem `STRICT`, status và hai bit cuối word.
- Không sửa đồng thời DAC, ADC và app. Giữ DAC làm golden reference, tập trung firmware ADS7861 trước.
- Không dùng đồ thị app làm bằng chứng ADC đúng khi raw frame còn sai.

## 10. Kết luận ngắn cho người tiếp nhận

DAC và đường phát sine đã được chứng minh hoạt động tốt. USB CDC đủ dùng cho các lệnh debug ngắn khi DAC chạy. Vấn đề trọng tâm còn lại là **timing/framing đọc ADS7861 qua SERIAL DATA A ở Mode II với RD và CONVST nối chung**. Hai word có dữ liệu thay đổi nhưng status luôn bị đọc thành A/A và có word không kết thúc bằng `00`, nên dữ liệu ADC hiện chưa đáng tin. Bước kế tiếp đã sẵn sàng trong firmware: khởi động lại DAC rồi so sánh `ADC_READ_TRIPLE` với `ADC_READ_TRIPLE1`, sau đó dùng logic analyzer khoanh vùng lệch bit/timing nếu status vẫn sai.

## 11. Cập nhật tiếp tục debug ngày 17/07/2026

Phần bàn giao phía trên mô tả trạng thái cũ. Kết quả mới đã thay đổi kết luận:

- Xác định cửa sổ nhận serial sớm một clock. Frame đúng được phục hồi bằng cách bỏ pipeline bit đầu; đường hardware SPI nhận 16 bit rồi dịch trái một bit vì bit cuối theo định dạng luôn là `0`.
- Thay `HAL_SPI_Receive()` bằng polling trực tiếp thanh ghi SPI2 có timeout. Cấu hình SPI2 hiện tại: CPOL LOW, CPHA 2EDGE, 1.125 MHz.
- Tắt `ADS7861_RELAX_FRAME_VALIDATION` trong build production.
- Sau khi prime pipeline một pair trong `ads7861_init()`, pair 0 đạt `500/500` frame strict qua hardware SPI.
- Mode IV trả đúng chuỗi status `0,1,2,3`, xác nhận parser status/data/trailing bits.
- Nguyên nhân B0 từng đọc âm full-scale không phải chip hỏng: mối hàn ADS7861 chân 4 `CHB0+` không tốt. Sau khi hàn lại chân 4, B0 về gần zero khi `CHB0+=CHB0-=2.5 V`.

Kiểm tra tuyến tính B0/Vin sau khi hàn:

| CHB0+ | Raw lý thuyết | Raw đo median |
|---:|---:|---:|
| 1.35 V | -942 | -945 |
| 1.65 V | -696 | -698 |
| 1.95 V | -451 | -454 |
| 2.50 V | 0 | -7 |

Với sine 20 kHz, 300 mV peak, Vin/B0 đo được khoảng `-933..-465`, strict `100/100`, phù hợp dải dự kiến.

Các sửa mapping/tích hợp đã thực hiện:

- `ADS B0 -> Vin` được đóng gói vào high 16 bit của capture buffer.
- `ADS A0 -> Vout` được đóng gói vào low 16 bit.
- Vin là đường trực tiếp nên luôn dùng calibration ADC1 range 0, không nhân hệ số relay x10/x100.
- Auto-range quan sát Vout/A0 ở low 16 bit, không quan sát Vin.
- Capture end-to-end ở AUTO cho Vin khoảng `211 mVrms`, `571 mVpp` với cấu hình sine 300 mV peak; DAC tiếp tục chạy và `TX_ERR=0`.

Việc còn lại:

- Xác minh sample interval thực tế; capture blocking hiện chưa được coi là 200 kSPS đồng bộ.
- Sau đó mới tối ưu timer/DMA, phase/frequency estimation và ứng dụng desktop.
- Pair 1/A1-B1 không dùng trong đường đo hiện tại; status khi chọn bằng A0 vẫn cần khảo sát riêng nếu sản phẩm cần pair 1.

## 12. Cập nhật tích hợp phát liên tục và app desktop

Với cấu hình `SINE, 200 Hz, 700 mV peak, offset 0, Fs yêu cầu 200 kSPS, 128 mẫu`, đã phát hiện hai vấn đề độc lập:

- LUT DAC bị giới hạn 256 điểm nhưng timer trước đây vẫn chạy ở `Fs=200 kHz`. Vì vậy tần số thực là `200000 / 256 = 781.25 Hz`, không phải 200 Hz, đồng thời ngắt DAC 200 kHz làm CPU kẹt khi `START` thu ADC.
- App dựng trục thời gian theo 200 kSPS yêu cầu nên 128 mẫu chỉ hiện 0.64 ms, trong khi chu kỳ 200 Hz là 5 ms. Đồ thị chỉ hiện một cung ngắn và DSP dùng sai sample rate.

Các sửa đổi đã áp dụng:

- Timer DAC chạy theo `freq * dac_lut_size`; với 200 Hz và 256 điểm là 51.2 kHz. Một vòng LUT luôn bằng đúng một chu kỳ tín hiệu.
- DAC chạy độc lập và liên tục trong lúc từng block ADC được chụp; `START` lặp lại không reset pha DAC.
- Firmware đo thời gian capture bằng DWT và trả `fs_actual` trong `GET_RESULT`.
- Measurement engine và app desktop dùng `fs_actual` thay cho Fs yêu cầu khi dựng trục thời gian và tính toán.
- `CONFIG` được áp dụng lại khi DAC đang chạy sẽ rebuild LUT rồi tiếp tục phát.

Kết quả test trực tiếp COM4 sau khi nạp production:

- 5/5 block `START` trả `OK`; CRC và chiều dài frame hợp lệ.
- `fs_actual` ổn định khoảng `17.05..17.09 kSPS`; 128 mẫu tương đương khoảng `7.49 ms`, đủ khoảng 1.5 chu kỳ ở 200 Hz.
- Vin raw khoảng `776..1921`, tương ứng sine đầy đủ gần `1.4 Vpp`.
- Không cắm DUT nên Vout chỉ ở quanh zero differential/noise; gain và phase hiện không có ý nghĩa.
- `DAC_TEST_STATUS`: `FREQ_HZ=200, UPDATE_HZ=51200, RUN=1, TX_ERR=0`.

App hiện dùng các block hữu hạn mới lặp lại khoảng mỗi 50 ms, không phải luồng ADC liên tục không khe hở. Mỗi block được tính độc lập và thay thế snapshot trên đồ thị. Muốn đạt 200 kSPS thật, lấy mẫu đều và streaming liên tục cần bước kiến trúc tiếp theo bằng timer/DMA; không được coi đường blocking hiện tại là 200 kSPS production.

Kiểm tra bổ sung ở `2000 Hz, 300 mV peak` cho thấy timer DAC 200 kHz vẫn làm app timeout dù oscilloscope còn thấy sine. Đã giới hạn đường cập nhật DAC bằng ngắt ở khoảng 50 kHz; cấu hình này dùng 25 điểm/chu kỳ. Kết quả 3/3 `START OK`, `fs_actual` khoảng 19.7–19.8 kSPS, Vin khoảng 598–599 mVpp, DAC `FREQ_HZ=2000, UPDATE_HZ=50000, RUN=1, TX_ERR=0`. Frame mẫu 512 byte có header `AA BB 03 02 00` và CRC khớp.
