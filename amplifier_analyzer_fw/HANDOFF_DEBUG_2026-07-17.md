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

App desktop đã đổi từ việc thay thế một block sang đồ thị rolling giữ 20 giây dữ liệu mẫu gần nhất. Bản đầu gắn timestamp wall clock và để hở idle gap nhưng không phù hợp cách người dùng cần quan sát; bản hiện tại nén khoảng nghỉ command/USB và đặt block kế tiếp ngay sau block trước theo `1/fs_actual`. RMS/frequency/gain/phase vẫn tính trên block liền mạch mới nhất, còn CSV/JSON chứa các mẫu đang giữ trong cửa sổ 20 giây sample-time. Đã qua `py_compile`, 4/4 unit test phân tích và smoke test offscreen; biên hai block liên tiếp cách đúng 50 us ở 20 kSPS.

## 13. Continuous acquisition bằng TIM2 + SPI2 DMA + USB sequence stream

Việc nối các block `START/GET_SAMPLES` cũ tạo gãy pha vì ADC dừng trong lúc command/USB chạy. Đã thay đường live của app bằng acquisition liên tục thật:

- SPI2 tăng theo checkpoint: 2.25 MHz đạt 500/500 strict frame; 4.5 MHz đạt 1000/1000; 9 MHz đạt 2000/2000. Chốt 9 MHz, không ép lên 18 MHz.
- Thêm `adc_stream.c/.h`: TIM2 tạo sample tick, DMA1 Channel 4/5 nhận/phát SPI2, ring buffer lưu Vin/Vout cùng sample sequence.
- Quét core DMA: 10/25/50 kSPS không invalid khi chưa tải USB; 75/100 kSPS thất bại. Khi DAC 50 kHz chạy song song, 40 kSPS đạt 5 giây với overrun/invalid bằng 0; 50 kSPS gây CPU/USB starvation.
- Thêm frame USB type `0x01`, payload gồm `first_sequence`, `fs`, `sample_count`, sau đó là Vin/Vout big-endian và CRC XOR.
- Quét end-to-end USB: 20, 25, 30 kSPS không thiếu sequence/CRC; 35 kSPS mất 61 mẫu trong 200 frame. Chốt production checkpoint hiện tại ở 30 kSPS.
- App dùng `LiveStreamWorker`, kiểm tra CRC và sequence trước khi append, gom 512 mẫu mỗi UI update, rolling 20 giây sample-time. Không còn vòng `START/GET_RESULT/GET_SAMPLES` cho live display.
- Soak thật 10.5 giây: PC nhận 307712 mẫu, sequence `0..307711`, không lỗi worker; firmware sau test báo `PRODUCED=307784, OVERRUN=0, INVALID=0, OVERWRITE=0`.
- Đồ thị refresh tối đa 10 Hz, pyqtgraph peak-downsampling/clip-to-view để có thể giữ 600000 mẫu (20 giây ở 30 kSPS) mà không nghẽn GUI. DSP dùng Fs stream thực 30 kSPS.

Full `SignalAnalyzerApp` đã được chạy offscreen với COM4 thật trong 3.5 giây: rolling history giữ 97280 mẫu/190 UI block, thời gian cuối 3.2426 s, mọi `dt` nằm quanh `33.333333 us`, communication OK, DSP nhận 30000 SPS và start/stop sạch. Đã sửa lỗi block mới từng ghi đè curve rolling: trong stream, `handle_samples()` chỉ làm DSP; rolling buffer là nơi duy nhất cập nhật curve/export. Khi bắt đầu live hardware, trường Fs trên UI tự chuyển về 30000 SPS để không hiển thị 200000 gây hiểu nhầm.

Checkpoint phần mềm/hardware tự động đã hoàn tất. Người dùng chỉ còn mở lại app và xác nhận trực quan waveform trên màn hình thật. Không được quảng cáo 200 kSPS: mức đã chứng minh end-to-end hiện tại là 30 kSPS.

### 13.1 Sửa gãy dạng sóng dù sequence USB liên tục

Quan sát GUI cho thấy sine vẫn có các cusp/điểm quay đầu dù sequence không thiếu. Sequence ban đầu chỉ đếm lần ISR được phục vụ, không phát hiện update-event timer bị coalesced khi USB priority cao giữ CPU quá chu kỳ 33 us. Đồng thời TIM2 có thể lấy mẫu đúng lúc MCP4822 đang settling.

Đã sửa:

- Khi TIM2/TIM3 có cùng rate, TIM2 được khởi tạo lệch nửa chu kỳ TIM3 để ADS7861 lấy mẫu giữa hai lần DAC update (khoảng 16.7 us sau DAC ở 30 kHz).
- DMA1 Channel 4, TIM2 và TIM3 chuyển priority 0; USB chuyển priority 2. Ở rate 30 kHz đã qualified, timer/DMA giữ timing trước USB thay vì để USB làm mất tick vật lý.
- Test 64000 mẫu sau sửa: host nhận khoảng 29.74 ksample/s, sine suy ra đúng 200.0 Hz, `DX_MAX=15 code`, không có bước >20 code, sequence/CRC lỗi 0; firmware `OVERRUN=0, INVALID=0, OVERWRITE=0`.
- Sửa false-positive clipping trong app: bỏ plateau test cho kênh gần phẳng dưới 1% full-scale và yêu cầu ít nhất 5 extrema liên tiếp. Test board: CH1 khoảng 0.601 Vpp, 199.65 Hz, CH1/CH2 đều `CLIP=False`, `SAT=False`; unit test 4/4 đạt.

### 13.2 Sửa CH1 bị hiển thị khoảng -100 V

Khi AUTO còn ở relay 10 V, app từng áp `adc1_r2_m = 100` cho cả CH1. Đây là sai mapping: ADS B0/Vin là đường trực tiếp, không qua relay, nên luôn phải dùng `adc1_r0_m/c`. Đã cố định CH1 dùng range 0; chỉ CH2/Vout dùng range relay hiện hành. Xác nhận board với raw Vin `1102..1594`: scale đúng là `-1.155..-0.554 V`, trong khi scale sai x100 cho `-115.5..-55.4 V`. Giá trị âm range-0 là điện áp vi sai `CHB0+ - 2.5 V`; node DAC vật lý với cấu hình 300 mV peak vẫn là khoảng `1.35..1.95 V`.

Theo yêu cầu UI, CH1/Vin hiện được trình bày dưới dạng điện áp node so với GND: sau calibration differential, app cộng lại VCM 2.5 V. Với raw `1102..1594`, kết quả hiển thị là `1.345..1.946 V`, Vpp vẫn `0.601 V`. Thay đổi DC convention này không ảnh hưởng Vrms AC, frequency, gain hoặc phase. Unit test 4/4 đạt.

## 14. Sửa reconnect sau stream và điều khiển cửa sổ xem

Root cause reconnect: command firmware `STOP` cũ chỉ gọi `test_controller_stop()` để dừng DAC, không gọi `adc_stream_stop()`. Nếu worker lỗi hoặc app đóng giữa stream, STM32 tiếp tục gửi frame nhị phân. Khi mở COM lại, `PING` đọc trúng binary backlog và thất bại cho tới khi USB CDC bị reset bằng cách rút cáp.

Đã sửa app độc lập với firmware:

- `stop_device_safely()` gửi `ADC_STREAM_STOP`, drain byte tới ACK, reset input buffer, sau đó gửi `STOP` và reset cả input/output.
- Normal stop, worker error, disconnect và closeEvent đều đi qua cleanup này; closeEvent gọi `LiveStreamWorker.request_stop()` thay vì chỉ `cancel_read()`.
- `serial_send_cmd` decode với replacement và không cố in binary ra console theo encoding hệ thống.
- Test backlog nhị phân chủ động: sau khi để stream tích frame cũ, cleanup/đóng/mở COM trả `PING OK` mà không rút USB.
- Test reconnect nhanh 8 vòng: cả 8 vòng mở lại đều `PING OK`; vòng cuối có sequence loss 1 mẫu nhưng cleanup vẫn phục hồi kết nối đúng.

Điều khiển view:

- Thêm `Follow live data / Bám theo dữ liệu mới`.
- Thêm `View window` từ 0.05 đến 20 s, mặc định 2 s.
- Bỏ chọn Follow để app không ép X-range; người dùng có thể zoom/pan tự do bằng pyqtgraph. Ring buffer vẫn giữ tối đa 20 s.

Firmware cũng đã patch để command `STOP` gọi `adc_stream_stop()` fail-safe và build production thành công (RAM 13656, flash 55660), nhưng chưa flash được patch STOP này: J-Link driver bị treo sau nhiều process upload chồng nhau; Windows từ chối restart PnP do thiếu quyền. App cleanup đã được test hoạt động với firmware hiện còn trên board. Cần rút/cắm lại riêng J-Link rồi upload firmware build hiện tại; không cần rút USB COM4 để app reconnect.

## 15. Khảo sát nâng sample rate sau khi ổn định app

Benchmark end-to-end trên firmware hiện còn ở board, DAC sine 200 Hz chạy đồng thời, 200 USB frame mỗi mức:

| Fs yêu cầu | Host rate | Sequence missing | Firmware overrun | Kết luận |
|---:|---:|---:|---:|---|
| 30 kSPS | 29.71 kSPS | 0 | 0 | đạt |
| 32 kSPS | 31.68 kSPS | 8 | 8 | không đạt |
| 34 kSPS | 33.55 kSPS | 110 | 111 | không đạt |
| 35 kSPS | 34.41 kSPS | 181 | 182 | không đạt |
| 36 kSPS | 35.35 kSPS | 199 | 200 | không đạt |

Nguyên nhân bottleneck đầu tiên đã xác định trong `adc_stream_usb_service()`: firmware tắt toàn bộ IRQ trong lúc scan/copy 128 mẫu (512 byte). Ở 30 kSPS chu kỳ là 33.3 us; từ 32 kSPS vùng critical đôi lúc dài hơn một chu kỳ, làm TIM2 đến khi `dma_word_state` còn bận và overrun tăng đúng bằng số sequence bị thiếu.

Đã patch nhưng chưa flash: main loop chỉ tắt IRQ vài lệnh để reserve 128 slot và advance consumer; bulk ring copy chạy khi timer/DMA interrupt vẫn bật. Production build thành công, RAM 13656 bytes, flash 55668 bytes. Cần cắm lại J-Link để nạp rồi quét lại 30–100 kSPS. Trần hiện đã chứng minh trên board vẫn là 30 kSPS; chưa có bằng chứng cho 200 kSPS.

### 15.1 Refactor ISR nhẹ và tăng buffer

Theo yêu cầu giảm công việc trong ngắt, đã refactor offline:

- DMA IRQ word B không parse/status-check/convert Vin-Vout nữa; chỉ ghi `word_a`, `word_b`, sequence low-16 vào raw ring, cập nhật producer counter và set `stream_data_ready` khi đủ block.
- Parse ADS status, swap A/B, signed conversion, validation, Vin/Vout packing và CRC chuyển sang `adc_stream_usb_service()` trong main context.
- TIM2 và DMA word-A vẫn phải pulse RD/CONVST và re-arm DMA vì đây là timing hard-real-time của board đang nối chung RD/CONVST; đã thay `HAL_GPIO_WritePin()` bằng direct BRR/BSRR + NOP trong ISR.
- Ring tăng 512 lên 1024 entry. Entry nén còn 6 byte (`word_a`, `word_b`, `sequence_low`) thay vì data+sequence 8 byte.
- USB chunk tăng 128 lên 256 mẫu. Main parse trực tiếp vào static USB frame, không tạo mảng copy 1 KB trên stack.
- Build production đạt: RAM `16224/20480 = 79.2%`, flash `55836/65536 = 85.2%`; app py_compile và unit test 4/4 đạt.

Độ trễ bình thường do chunk 256: 8.53 ms ở 30 kSPS, 2.56 ms ở 100 kSPS, 1.28 ms ở 200 kSPS. Ring 1024 hấp thụ tối đa khoảng 34.1/10.24/5.12 ms tương ứng. Buffer không giảm throughput trung bình: raw hai kênh vẫn cần 120/400/800 kB/s ở 30/100/200 kSPS.

Chưa flash/test được bản này vì J-Link thấy VTref 3.26–3.28 V nhưng không initialize DAP ở cả SWD 1 MHz và 100 kHz, kể cả connect-under-reset. Cần kiểm tra lại GND, SWDIO/PA13, SWCLK/PA14 và NRST rồi nạp/test. Không được coi refactor này đã chạy trên board cho tới khi upload thành công và sequence/overrun stress đạt.

### 15.2 Kết quả sau khi nạp refactor ISR/buffer

J-Link đã kết nối lại và production refactor đã được nạp/test trực tiếp trên COM4:

- `ADC_READ_ONCE` strict đạt `2000/2000`; không lỗi SPI/status/trailing bits.
- 30 kSPS trong 10.004 s: host nhận 300032 mẫu, CRC/sequence lỗi 0; firmware `OVERRUN=0, INVALID=0, OVERWRITE=0`.
- Phát hiện stop/start cũ có thể để pending DMA và làm lệch pipeline ADS7861. Đã sửa `adc_stream_stop()` để disable/clear DMA IRQ, drain SPI, xóa pending IRQ; `adc_stream_start()` prime tối đa ba cặp và chỉ start khi có strict-valid frame. Stress 18 lần start/stop ở 30/54/60 kSPS không còn `INVALID`.
- Tối ưu parse main: kiểm tra status/trailing bits và đổi two's-complement sang transport code trực tiếp, không gọi `ads7861_parse_word()` nhiều lần cho mỗi mẫu.
- ADC stream khi DAC dừng: 60, 61, 62, 63, 64 kSPS đều sạch 5 s; 64.5 kSPS bắt đầu overrun. Mốc có biên an toàn là 60 kSPS.
- ADC stream khi DAC sine 200 Hz cập nhật 50 kHz: 35/40/45 kSPS sạch 5 s; 50 kSPS bắt đầu ring overwrite do main/USB không theo kịp.
- Soak production-load ở ADC 45 kSPS + DAC update 50 kHz trong 30.001 s: host nhận 1349888 mẫu (44994.4 SPS), 5273 frame, CRC/sequence lỗi 0; firmware `PRODUCED=1350111, OVERRUN=0, INVALID=0, OVERWRITE=0`; DAC `TX_ERR=0`.
- Vin raw trong soak là `1095..1591`, phù hợp sine khoảng 0.6 Vpp đã xác nhận bằng oscilloscope.
- App `LiveStreamWorker.STREAM_FS` đã nâng từ 30 kSPS lên mốc đã chứng minh 45 kSPS.

Build cuối: RAM `16224/20480 = 79.2%`, flash khoảng `55900/65536 = 85.3%`.

Chưa đạt 200 kSPS continuous. Giới hạn hiện tại không phải do riêng core 72 MHz hoặc riêng SPI: kiến trúc còn TIM2 IRQ + hai DMA-complete IRQ cho mỗi cặp ADC, đồng thời TIM3 ISR polling SPI1 tới 50 kHz. Muốn tiến gần 200 kSPS phải thay đường ADC bằng timer-generated RD/CONVST và circular/double-buffer DMA (IRQ theo nửa/full buffer), đồng thời chuyển DAC sang SPI1 DMA/timer trigger hoặc giảm update IRQ; sau đó mới tăng SPI2 và benchmark lại. Tăng ring tiếp chỉ kéo dài thời gian trước overwrite, không sửa throughput trung bình.

### 15.3 Checkpoint 55 kSPS với DAC 50 kHz

- SPI2 tăng từ 9 lên 18 MHz và đạt lại `2000/2000` lệnh `ADC_READ_ONCE` strict-valid.
- IRQ priority tách thành ADC TIM2/DMA = 0, USB = 1, DAC TIM3 = 2 để USB không bị DAC polling làm starvation.
- Một cặp ADC dùng một RX DMA 4 byte; half-transfer chỉ pulse RD/CONVST và rearm TX 2 byte cho word B, transfer-complete mới ghi raw ring. Không còn tháo/lắp lại toàn bộ RX DMA giữa word A/B.
- Soak ADC 55 kSPS + DAC sine 200 Hz/update 50 kHz trong 30.004 s: host nhận `1650176` mẫu (`54998.4 SPS`), 6446 frame; CRC/sequence lỗi 0; firmware `PRODUCED=1650392, OVERRUN=0, INVALID=0, OVERWRITE=0`; DAC `TX_ERR=0`.
- Vin raw `1096..1591`, vẫn đúng sine analog khoảng 0.6 Vpp.
- App live stream nâng lên 55 kSPS. Đây là checkpoint +10 kSPS đầu tiên sau commit 45 kSPS.

### 15.4 Checkpoint 65 kSPS với DAC 50 kHz

- USB chunk tăng 256 lên 512 mẫu; RAM build khoảng 84.3%. Độ trễ block khoảng 7.88 ms ở 65 kSPS.
- Thêm DWT telemetry `BUILD_CYC`/`SEND_CYC` vào `ADC_STREAM_STATUS` để tách thời gian đóng frame và USB transmit.
- SPI1 DAC chuyển từ hai access 8-bit sang một access 16-bit cho mỗi frame MCP4822. CS vẫn bao đúng 16 clock, nhưng giảm polling trong 50000 TIM3 IRQ/s.
- Soak ADC 65 kSPS + DAC update 50 kHz trong 30.003 s: host nhận `1949184` mẫu (`64966.6 SPS`), 3807 frame; CRC/sequence lỗi 0; firmware `PRODUCED=1950166, OVERRUN=0, INVALID=0, OVERWRITE=0`; DAC `TX_ERR=0`.
- Vin raw `1096..1592`, xác nhận DAC 16-bit vẫn phát đúng sine. `BUILD_CYC_MAX=314601`, `SEND_CYC_MAX=215592`.
- App live stream nâng lên 65 kSPS. Đây là checkpoint +10 kSPS thứ hai.

### 15.5 Checkpoint 75 kSPS với DAC 50 kHz

- CRC XOR được tính ngay khi pack sample, bỏ lần quét lại toàn bộ payload; hot USB service compile riêng ở `O3`.
- `protocol_send_raw_async()` và hai frame buffer cho phép USB gửi buffer A trong khi main build buffer B. Chỉ giữ tối đa một frame pending, không sửa buffer USB đang sở hữu.
- CDC RX/TX buffer mặc định giảm 1024 xuống 512 byte; frame stream dùng double-buffer riêng. Build RAM `18304/20480 = 89.4%`, flash khoảng 86.0%.
- Soak ADC 75 kSPS + DAC update 50 kHz trong 30.003 s: host nhận `2249728` mẫu (`74982.3 SPS`), 4394 frame; CRC/sequence lỗi 0; firmware `PRODUCED=2250550, OVERRUN=0, INVALID=0, OVERWRITE=0`; DAC `TX_ERR=0`.
- Vin raw `1096..1590`. Async USB giảm `SEND_CYC_MAX` xuống 7032 cycles; `BUILD_CYC_MAX=277777`.
- App live stream nâng lên 75 kSPS. Đây là checkpoint +10 kSPS thứ ba.

### 15.6 Checkpoint 85 kSPS với DAC 50 kHz

- Ring tăng 1024 lên 2048 mẫu, lưu word A/B thành hai mảng 16-bit aligned và sequence anchor 16-bit theo block 512; khi quá tải drop nguyên block để giữ alignment và host thấy sequence jump.
- Finite capture tối đa giảm 512 xuống 256 mẫu; CDC RX/TX mặc định giảm 512 xuống 256 byte. Build RAM `18832/20480 = 92.0%`, flash khoảng 86.2%.
- DMA transfer-complete không còn tạo IRQ: TIM2 tick kế tiếp xác nhận TC, commit mẫu trước rồi start mẫu mới. ADC giảm từ ba xuống hai IRQ/mẫu; nếu DMA chưa xong đúng tick thì `OVERRUN` tăng.
- DAC SPI1 chạy pipeline: TIM3 hoàn tất/latch frame trước rồi launch frame 16-bit mới, không busy-wait trong ISR; STOP flush frame cuối. Priority cuối: ADC 0, DAC 1, USB 2.
- Đo waveform ở 85 kSPS: FFT peak `200.062 Hz`, crossing hysteresis `200.01 Hz`, Vin raw `1096..1590`; xác nhận DAC vẫn đúng 200 Hz.
- Soak ADC 85 kSPS + DAC update 50 kHz trong 30.004 s: host nhận `2549760` mẫu (`84980.1 SPS`), 4980 frame; CRC/sequence lỗi 0; firmware `PRODUCED=2550726, OVERRUN=0, INVALID=0, OVERWRITE=0`; DAC `TX_ERR=0`.
- App live stream nâng lên 85 kSPS. Đây là checkpoint +10 kSPS thứ tư.

### 15.7 Checkpoint 95 kSPS với DAC 50 kHz

- DMA1 Channel 4/5 và SPI2 DMA request được cấu hình cố định một lần trong `adc_stream_start()`; hot tick chỉ clear flag, reload `CNDTR` và enable channel.
- Tick kế tiếp commit transfer đã hoàn tất mà không tháo SPI DMA request hay polling BSY. Điều này giảm mạnh thời gian TIM2 ISR/main bị preempt.
- Soak ADC 95 kSPS + DAC update 50 kHz trong 30.005 s: host nhận `2849280` mẫu (`94961.5 SPS`), 5565 frame; CRC/sequence lỗi 0; firmware `PRODUCED=2850149, OVERRUN=0, INVALID=0, OVERWRITE=0`; DAC `TX_ERR=0`.
- Vin raw `1096..1591`; `BUILD_CYC_MAX=223614`, `SEND_CYC_MAX=5182`.
- App live stream nâng lên 95 kSPS. Đây là checkpoint +10 kSPS thứ năm.

### 15.8 Mục tiêu cuối 100 kSPS với DAC 50 kHz

- Test 10 s: host nhận `999424` mẫu (`99923.9 SPS`), CRC/sequence lỗi 0; firmware `PRODUCED=1000361, OVERRUN=0, INVALID=0, OVERWRITE=0`; FFT Vin peak `199.8901 Hz`, DAC `TX_ERR=0`.
- Soak cuối 60.004 s: host nhận `5999616` mẫu (`99986.4 SPS`), 11718 frame; CRC/sequence/junk lỗi 0; firmware `PRODUCED=6000631, OVERRUN=0, INVALID=0, OVERWRITE=0`; DAC `TX_ERR=0`.
- Vin raw trong soak `1097..1590`. Worst observed `BUILD_CYC=347865`, `SEND_CYC=5714`; block 512 tại 100 kSPS có ngân sách khoảng 368640 cycles, vì vậy đã đạt nhưng biên timing còn khoảng vài phần trăm ở worst case.
- App live stream nâng lên 100 kSPS. Đây là mục tiêu continuous end-to-end đã chứng minh với DAC update 50 kHz, không còn là giá trị lý thuyết.
- Smoke test `LiveStreamWorker` thật ở 100 kSPS trong 3 s: 558 UI block/285696 mẫu, worker error 0, QThread stop bình thường; firmware sau stop `OVERRUN=0, INVALID=0, OVERWRITE=0`.

### 15.9 Checkpoint 110 kSPS và DAC timer-DMA

- Continuous stream dùng frame type `0x04`: hai kênh 12-bit được pack lossless thành 3 byte/mẫu; app vẫn nhận tương thích frame `0x01` cũ.
- ISR ADC chỉ validate/chuyển code và lưu một word 24-bit trong ring. Main pack bốn mẫu thành ba word 32-bit aligned, tính CRC theo word; USB payload giảm từ 4 xuống 3 byte/mẫu.
- DAC không còn TIM3 IRQ theo từng điểm. TIM3_CH1/DMA1_CH6 đưa CS high, TIM3_CH3/DMA1_CH2 đưa CS low, TIM3 update/DMA1_CH3 ghi frame 16-bit vào SPI1 DR. Chỉ DMA TC mỗi chu kỳ LUT tạo IRQ (~200 IRQ/s ở sine 200 Hz).
- DMA ADC đặt very-high, DMA DAC medium để bảo vệ cửa sổ A/B. DAC DMA được xác nhận Vin raw `1100..1600`, FFT `199.967 Hz`, khoảng 50 kframe/s.
- Soak ADC 110 kSPS + DAC update 50 kHz trong 30.004 s: host nhận `3297792` mẫu (`109911.8 SPS`), 6441 frame; CRC/sequence lỗi 0; firmware `PRODUCED=3298255, OVERRUN=0, INVALID=0, OVERWRITE=0`; DAC `TX_ERR=0`.
- Build cuối checkpoint: RAM khoảng 89.5%, flash khoảng 87.1%. App live stream nâng lên 110 kSPS.

### 15.10 Checkpoint 120 kSPS

- 120 kSPS ban đầu lỗi khoảng 100--118 mẫu/s khi bật USB, nhưng ADC/SPI chạy nội bộ 10 giây ở 120 kSPS có `OVERRUN=0`, chứng minh đây chưa phải giới hạn ADC hoặc SPI.
- Root cause là main khóa toàn bộ IRQ khi snapshot ring counter trước mỗi frame USB. Hai counter 32-bit đã aligned và được truy cập nguyên tử trên Cortex-M3; đường ring là single-producer/single-consumer nên bỏ global IRQ mask và dùng snapshot không khóa.
- Soak ADC 120 kSPS + DAC update 50 kHz trong 30.000 s: host nhận `3599360` mẫu (`119978.7 SPS`), 7030 frame; CRC/sequence/junk lỗi 0; firmware `PRODUCED=3599984, OVERRUN=0, INVALID=0, OVERWRITE=0`; DAC `TX_ERR=0`.
- Build production: RAM 18328/20480 byte (89.5%), flash 57012/65536 byte (87.0%). App live stream nâng lên 120 kSPS.

### 15.11 Checkpoint 130 kSPS

- Quét timing nội bộ cho thấy bản 120 kSPS cũ sạch ở 122 kSPS nhưng bắt đầu overrun từ 124 kSPS. Critical path còn ghi LOW lặp lại và chèn 6 NOP cho mỗi xung RD/CONVST.
- Hai call-site đã giữ RD/CONVST LOW trước khi pulse. Bỏ GPIO BRR dư và giữ 2 NOP sau cạnh HIGH vẫn vượt yêu cầu HIGH tối thiểu 15 ns; strict ADS frame validation tiếp tục báo `INVALID=0`.
- Sau tối ưu: ADC nội bộ sạch ở 124/126/128/130 kSPS; 135 kSPS bắt đầu có overrun nên chưa được dùng làm checkpoint.
- Soak ADC 130 kSPS + DAC update 50 kHz trong 30.000 s: host nhận `3896832` mẫu (`129894.4 SPS`), 7611 frame; CRC/sequence/junk lỗi 0; firmware `PRODUCED=3897342, OVERRUN=0, INVALID=0, OVERWRITE=0`; DAC `TX_ERR=0`.
- Build production: RAM 18328/20480 byte (89.5%), flash 56932/65536 byte (86.9%). App live stream nâng lên 130 kSPS.

### 15.12 Checkpoint 140 kSPS

- Refactor pipeline timer: chụp 4 byte DMA đã hoàn tất, lập tức arm conversion/DMA kế tiếp, sau đó mới xử lý mẫu cũ. CPU và SPI được chạy chồng lấp thay vì để SPI chờ parse/store.
- Dời strict frame validation, đổi two's-complement sang offset-binary và tạo packed-12 từ ISR sang main khi build frame USB. ISR chỉ giữ raw 32-bit và metadata ring, giảm critical interrupt time.
- ADC nội bộ sạch đến 150 kSPS; 160 kSPS làm main bị starvation nên không được coi là usable.
- Soak ADC 140 kSPS + DAC update 50 kHz trong 30.000 s: host nhận `4201472` mẫu (`140049.1 SPS`), 8206 frame; CRC/sequence/junk lỗi 0; firmware `PRODUCED=4202421, OVERRUN=0, INVALID=0, OVERWRITE=0`; DAC `TX_ERR=0`.
- Build production: RAM 18328/20480 byte (89.5%), flash 57172/65536 byte (87.2%). App live stream nâng lên 140 kSPS.

### 15.13 Biên tối đa sau checkpoint 140 kSPS

- Tối ưu tiếp vòng raw-to-packed: thứ tự A/B được xác định một lần ở frame đầu stream, strict status vẫn kiểm tra mọi mẫu nhưng counter invalid được gom theo nhóm 4; phép đổi raw 32-bit sang packed-24 dùng biểu thức mask/shift trực tiếp.
- Quét end-to-end 4 s với DAC 50 kHz: 142/144/145 kSPS sạch (`OVERRUN=INVALID=OVERWRITE=0`, CRC/sequence 0); 146 kSPS bắt đầu `OVERWRITE=2560`, 148 kSPS `OVERWRITE=101888`; 150 kSPS không usable. Vì checkpoint theo bước 10 kSPS nên app/production vẫn giữ 140 kSPS, còn 145 kSPS chỉ là headroom ngắn hạn chưa qualify soak.
- ADC/SPI nội bộ đã sạch đến 150 kSPS. Giới hạn hiện tại là CPU đóng gói cộng transport USB CDC single-PMA-buffer, không phải clock 72 MHz nói chung và không phải SPI2 18 MHz.
- Đã thử bật PMA double-buffer cho CDC IN 0x81 nhưng ST CDC/PCD state machine hiện tại write-timeout ngay từ PING; thay đổi đã rollback. Muốn vượt 150 kSPS lossless cần refactor đồng bộ callback/state machine USB double-buffer hoặc chuyển transport USB riêng, không chỉ đổi `PCD_DBL_BUF`.

### 15.14 DAC DMA 200 kupdate/s đồng thời ADC 140 kSPS

- Xóa policy cũ `DAC_MAX_ISR_RATE_HZ=50000`; giới hạn production mới là `DAC_MAX_DMA_RATE_HZ=200000`, tương ứng chu kỳ 5 us và còn khoảng 0.5 us so với settling DAC khoảng 4.5 us.
- TIM3 + DMA1 Ch2/3/6 vẫn điều khiển CS và SPI1 hoàn toàn bằng phần cứng. DMA Ch3 không còn phát TC interrupt mỗi vòng LUT; chỉ bật TE interrupt khi transfer error. Với sine 20 kHz việc này loại bỏ 20,000 IRQ/s không cần thiết.
- DAC và ADC độc lập: DAC luôn chọn mật độ điểm lớn nhất tới 200 kupdate/s; `N=min(256, floor(200000/f_signal))`, tối thiểu 4 điểm. Ví dụ 20 kHz dùng 10 điểm/chu kỳ và 200 kupdate/s; 200 Hz dùng đủ 256 điểm và 51.2 kupdate/s.
- Sửa parser CONFIG: key `FS` trước đây match nhầm chuỗi con trong `OFFSET_MV`, làm FS luôn giữ giá trị cũ. Parser mới chỉ nhận key ở đầu field hoặc ngay sau dấu phẩy.
- Quét sine 20 kHz ở 80/100/120/140/160/180/200 kupdate/s đồng thời ADC/USB 140 kSPS, mỗi mức 3 s: CRC/sequence/junk 0; ADC `OVERRUN=INVALID=OVERWRITE=0`; DAC `TX_ERR=0`; raw Vin luôn có tín hiệu 20 kHz.
- Soak 30.000 s tại DAC 200 kupdate/s + ADC 140 kSPS: host `4199936` mẫu (`139997.9 SPS`), 8203 frame; CRC/sequence/junk 0; ADC `PRODUCED=4200959, OVERRUN=0, INVALID=0, OVERWRITE=0`; DAC `TX_ERR=0`, raw Vin `1100..1593`.
- Kiểm tra lại đúng cấu hình app `CONFIG.FS=140000`: status DAC vẫn `UPDATE_HZ=200000`; stream ADC 140 kSPS 10 s nhận `1399296` mẫu, mọi counter lỗi bằng 0.
