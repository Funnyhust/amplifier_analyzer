# Tổng hợp session tối ưu firmware, ứng dụng và thu thập kết quả thực nghiệm

**Thời gian thực hiện:** 17--18/07/2026  
**Repository:** `D:\hust\amplifier_analyzer\amplifier_analyzer`  
**Nhánh:** `master`  
**Phần cứng:** STM32F103C8T6 + MCP4822 + ADS7861  
**Kết nối khi kiểm nghiệm:** J-Link và USB CDC `COM4`

## 1. Mục tiêu và kết quả cuối session

Session bắt đầu từ trạng thái DAC đã phát được tín hiệu nhưng ADC/USB mới phù hợp cho debug tốc độ thấp. Mục tiêu là xác nhận từng tầng theo đúng thứ tự, sau đó tối ưu firmware mà không làm mất tính ổn định:

1. Xác nhận framing và dữ liệu ADS7861.
2. Thay capture rời rạc bằng ADC streaming liên tục.
3. Tăng tốc độ lấy mẫu từng checkpoint có soak test và commit riêng.
4. Chuyển đường phát MCP4822 sang timer + DMA để loại bỏ ngắt theo từng mẫu.
5. Giữ ADC 140 kSPS trong khi DAC cập nhật tối đa 200 ksample/s.
6. Tách COM reader khỏi GUI để app không làm mất mẫu.
7. Sửa cách hiển thị, mapping hai kênh và hệ số ba dải đo.
8. Chạy ma trận test phần cứng thật và chụp ảnh ứng dụng tự động cho báo cáo.

Trạng thái cuối đã được chứng minh:

- ADC streaming production đặt `140000 SPS`; timer thực tế báo khoảng `140077 SPS`.
- Soak 30 giây tại ADC 140 kSPS: không lỗi CRC, sequence, overrun, invalid frame hoặc overwrite.
- DAC dùng timer + DMA, cập nhật tối đa `200000 sample/s`.
- ADC 140 kSPS và DAC 200 ksample/s chạy đồng thời ổn định.
- Tín hiệu DAC 20 kHz dùng 10 điểm/chu kỳ ở 200 ksample/s.
- App desktop đọc stream bằng process riêng, không còn tự dừng sau 50--120 ms do GUI giữ GIL.
- Chín cấu hình phần cứng thật đã được chụp thành waveform, bảng kết quả và metadata trong `report/images/result_app/`.

> Lưu ý đơn vị: 140 kSPS là tốc độ lấy mẫu ADC, không phải tần số tín hiệu 140 kHz. Tương tự, 200 ksample/s là tốc độ cập nhật DAC; tần số sine được cấu hình độc lập.

## 2. Bring-up ADS7861 và lỗi phần cứng đã tìm được

### 2.1 Framing serial

ADS7861 ban đầu được đọc chậm bằng GPIO bit-bang để quan sát framing. Dữ liệu thay đổi nhưng status thường bị đọc thành A/A và trailing bits không đúng, vì vậy chưa thể tin raw ADC.

Kết quả debug cuối:

- Cửa sổ nhận serial bị sớm một clock.
- Hardware SPI2 được dùng với CPOL LOW, CPHA 2EDGE.
- Frame 16 bit nhận từ SPI được căn lại theo pipeline thực tế.
- Thay `HAL_SPI_Receive()` bằng polling trực tiếp thanh ghi trong giai đoạn xác nhận.
- Tắt `ADS7861_RELAX_FRAME_VALIDATION` ở production.
- Sau khi prime pipeline, pair 0 đạt 500/500 frame strict.
- Mode IV trả đúng chuỗi status `0,1,2,3`, xác nhận parser status/data/trailing bits.

Mapping đúng của phần cứng:

- ADS B0 → CH1/Vin, đóng gói vào 16 bit cao.
- ADS A0 → CH2/Vout, đóng gói vào 16 bit thấp.
- CH1 là đường trực tiếp, không đi qua relay range.
- CH2 là đường DUT/AFE và chịu tác động của relay range.

### 2.2 Mối hàn chân 4 ADS7861

B0 từng đọc gần âm full-scale dù hai đầu vào được đặt cùng mức 2,5 V. Nguyên nhân không phải chip hỏng hay parser sai mà là mối hàn chân 4 `CHB0+` không tốt. Sau khi hàn lại, B0 về gần zero.

Kiểm tra tuyến tính sau sửa mối hàn:

| CHB0+ | Raw lý thuyết | Raw median đo được |
|---:|---:|---:|
| 1,35 V | -942 | -945 |
| 1,65 V | -696 | -698 |
| 1,95 V | -451 | -454 |
| 2,50 V | 0 | -7 |

Kết quả này là mốc xác nhận ADS7861, parser và đường analog Vin đã hoạt động đúng trước khi tối ưu tốc độ.

## 3. Từ capture blocking đến stream ADC liên tục 30 kSPS

Thiết kế cũ dùng `START/GET_RESULT/GET_SAMPLES` theo từng block. ADC dừng trong lúc firmware xử lý command và USB, nên khi app nối các block lại sẽ có gãy pha và khoảng trống giả.

Kiến trúc mới được thêm trong:

- `amplifier_analyzer_fw/Core/Inc/adc_stream.h`
- `amplifier_analyzer_fw/Core/Src/adc_stream.c`

Các thành phần chính:

- TIM2 tạo nhịp lấy mẫu đều.
- SPI2 nhận hai word ADS7861.
- DMA1 Channel 4/5 phục vụ SPI2 RX/TX.
- Ring buffer lưu mẫu cùng sequence liên tục.
- USB frame chứa `first_sequence`, sample rate và số mẫu.
- Host kiểm tra header, length, CRC XOR và continuity của sequence.

Checkpoint end-to-end ban đầu:

- 20, 25 và 30 kSPS sạch qua USB.
- 35 kSPS bắt đầu mất sequence với kiến trúc ban đầu.
- Production được chốt tạm ở 30 kSPS tại commit `8efc6ca`.
- Soak khoảng 10,5 giây nhận 307712 mẫu liên tục, không overrun/invalid/overwrite.

Giới hạn ở giai đoạn này không chỉ do SPI. Tải gồm ISR lấy mẫu, tạo frame USB, sao chép dữ liệu, CRC, USB CDC và GUI desktop.

## 4. Quá trình tăng từ 30 kSPS lên 140 kSPS

Mỗi mức ổn định được test phần cứng thật và commit riêng. Không tăng thẳng một lần rồi đoán nguyên nhân.

| Commit | Checkpoint | Nội dung chính |
|---|---:|---|
| `8efc6ca` | 30 kSPS | ADC continuous stream bằng TIM2/SPI2/DMA và sequence frame. |
| `8353c5e` | 55 kSPS | Giảm overhead đường lấy mẫu/stream. |
| `b177877` | 65 kSPS | Tối ưu critical path tiếp theo. |
| `f46526d` | 75 kSPS | Xác nhận stream lossless ở tải cao hơn. |
| `1eeef9c` | 85 kSPS | Soak 30 giây với DAC 50 ksample/s, không lỗi. |
| `7891bb3` | 95 kSPS | Giữ SPI DMA request, reload DMA thay vì tháo/lắp mỗi tick. |
| `82624f7` | 100 kSPS | Soak 60 giây, gần 6 triệu mẫu, không lỗi. |
| `26408b0` | 110 kSPS | Pack hai mẫu 12-bit thành 3 byte và chuyển DAC sang timer-DMA. |
| `893642f` | 120 kSPS | Bỏ khóa toàn bộ IRQ khi snapshot ring counter. |
| `645a413` | 130 kSPS | Rút ngắn pulse RD/CONVST và bỏ GPIO write/NOP dư. |
| `104a326` | 140 kSPS | Chồng lấp arm conversion mới với xử lý mẫu cũ; dời parse/pack khỏi ISR. |
| `1144fed` | headroom 145 kSPS | Tối ưu raw-to-packed; 145 kSPS sạch ngắn hạn nhưng không qualify soak. |

### 4.1 Các tối ưu quan trọng

#### ISR ngắn và pipeline chồng lấp

- ISR ưu tiên arm conversion/DMA kế tiếp ngay sau khi chụp DMA cũ.
- Validation strict, đổi two's-complement và pack 12-bit được dời sang main khi build USB frame.
- CPU xử lý mẫu cũ trong khi SPI đang nhận mẫu mới.
- Callback/ngắt chủ yếu cập nhật trạng thái và ring metadata.

#### Giảm payload USB

Hai kênh 12-bit được pack lossless thành 24 bit, tức 3 byte/mẫu thay vì 4 byte/mẫu. App vẫn tương thích frame cũ trong giai đoạn chuyển tiếp.

#### Ring buffer single-producer/single-consumer

Hai counter 32-bit aligned được truy cập nguyên tử trên Cortex-M3. Bỏ global IRQ mask khi main snapshot counter đã giải quyết lỗi mất khoảng 100--118 mẫu/s ở 120 kSPS.

#### Tối ưu pulse RD/CONVST

Loại bỏ GPIO write LOW lặp lại và giảm NOP dư, vẫn giữ pulse HIGH vượt yêu cầu tối thiểu của ADS7861. Strict validation tiếp tục cho `INVALID=0`.

### 4.2 Kết quả 140 kSPS

Soak ADC 140 kSPS với DAC 50 ksample/s trong 30 giây:

- Host nhận 4.201.472 mẫu, khoảng 140.049 SPS theo thời gian host.
- Firmware tạo 4.202.421 mẫu.
- `OVERRUN=0`.
- `INVALID=0`.
- `OVERWRITE=0`.
- CRC/sequence/junk lỗi 0.
- DAC `TX_ERR=0`.

Sau tối ưu headroom:

- 142, 144 và 145 kSPS sạch trong quét ngắn.
- 146 kSPS bắt đầu overwrite.
- 148 kSPS overwrite lớn.
- 150 kSPS không usable end-to-end dù ADC/SPI nội bộ vẫn có thể sạch.

Vì vậy production giữ 140 kSPS. Giới hạn cuối nằm ở đóng gói CPU + USB CDC single-PMA-buffer, không phải SPI2 đơn thuần. Việc bật PMA double-buffer trực tiếp đã làm CDC timeout và được rollback; muốn vượt đáng kể cần refactor state machine USB hoặc đổi transport/MCU.

## 5. Chuyển DAC sang timer + DMA và nâng lên 200 ksample/s

### 5.1 Vấn đề đường ngắt cũ

Ban đầu TIM3 phát DAC bằng ISR theo từng điểm. Khi DAC update 50--200 ksample/s, số ngắt lớn cạnh tranh trực tiếp với ADC và USB. Đặc biệt, phát 20 kHz với LUT nhiều điểm có thể tạo hàng chục nghìn đến hàng trăm nghìn lần phục vụ mỗi giây.

### 5.2 Kiến trúc DMA

Đường MCP4822 mới dùng hoàn toàn timer + DMA:

- TIM3_CH1 / DMA1 Channel 6 điều khiển CS lên HIGH.
- TIM3_CH3 / DMA1 Channel 2 điều khiển CS xuống LOW.
- TIM3 update / DMA1 Channel 3 ghi frame 16-bit vào SPI1 DR.
- DMA ADC có priority very-high; DMA DAC dùng medium.
- Không còn interrupt theo từng sample DAC.
- DMA DAC chỉ giữ transfer-error interrupt; không phát TC interrupt không cần thiết mỗi vòng LUT.

Các file chính:

- `amplifier_analyzer_fw/Core/Inc/mcp4822.h`
- `amplifier_analyzer_fw/Core/Src/mcp4822.c`
- `amplifier_analyzer_fw/Core/Src/test_controller.c`
- `amplifier_analyzer_fw/Core/Src/command_parser.c`

### 5.3 Chính sách tốc độ DAC

- Giới hạn mới: `DAC_MAX_DMA_RATE_HZ = 200000`.
- Số điểm: `N = min(256, floor(200000 / f_signal))`, tối thiểu 4 điểm.
- 200 Hz dùng đủ 256 điểm, update 51,2 ksample/s.
- 20 kHz dùng 10 điểm/chu kỳ, update 200 ksample/s.
- Chu kỳ update nhanh nhất là 5 µs, chỉ còn khoảng 0,5 µs so với settling time điển hình 4,5 µs của MCP4822; đây là biên analog cần lưu ý.

Sửa kèm theo: parser `CONFIG` trước đây có thể match nhầm key `FS` nằm trong `OFFSET_MV`. Parser mới chỉ nhận key ở đầu field hoặc sau dấu phẩy.

### 5.4 Kết quả chạy đồng thời ADC và DAC

Đã quét DAC 80/100/120/140/160/180/200 ksample/s trong khi ADC và USB chạy 140 kSPS. Tất cả mức đều:

- CRC/sequence/junk lỗi 0.
- ADC overrun/invalid/overwrite bằng 0.
- DAC `TX_ERR=0`.
- Vin raw vẫn chứa đúng tín hiệu 20 kHz.

Soak cuối 30 giây ở DAC 200 ksample/s + ADC 140 kSPS:

- Host nhận 4.199.936 mẫu, khoảng 139.998 SPS.
- Firmware tạo 4.200.959 mẫu.
- Mọi counter lỗi bằng 0.
- DAC `TX_ERR=0`.

Commit checkpoint: `ea11f00 perf: raise DAC DMA rate to 200 kSPS`.

## 6. Ứng dụng desktop và stream ổn định

### 6.1 Vì sao firmware sạch nhưng app vẫn tự dừng

Direct-COM soak cho thấy firmware sạch, nhưng app từng dừng sau 50--120 ms và báo sequence loss. Nguyên nhân là GUI/FFT/PyQtGraph giữ Python GIL, khiến `QThread` đọc COM không drain Windows CDC kịp.

Giải pháp cuối:

- `app_desktop/stream_reader_process.py` mở COM trong process Python riêng.
- Process này parse header/length/CRC/sequence độc lập với GUI.
- Block mẫu được chuyển lossless về GUI qua localhost TCP.
- Socket buffer đặt 4 MiB.
- GUI chỉ enqueue block; timer xử lý FFT/metrics/plot tối đa khoảng 5 Hz.
- Khi stop, helper process đóng; GUI mở lại COM và gửi `STOP`, không cần rút USB.

Visible-GUI smoke ở 140 kSPS chạy ổn định, start/stop/restart không cần cắm lại thiết bị.

### 6.2 Sửa đồ thị răng cưa/tam giác giả

ADC raw và oscilloscope là sine nhưng app từng hiển thị tam giác/răng cưa. Có hai nguyên nhân hiển thị:

1. Min/max decimation gán cực trị vào đầu/cuối bucket thay vì timestamp thật.
2. App decimate toàn bộ history 20 giây trước khi crop cửa sổ 2 giây, làm vùng zoom chỉ còn rất ít điểm mỗi chu kỳ.

Cách sửa:

- Crop đúng cửa sổ thời gian cần xem trước.
- Sau đó downsample đều theo timestamp thật.
- DSP/FFT tiếp tục dùng raw block, không dùng dữ liệu plot đã giảm mẫu.
- Firmware gửi `actual_fs` tính từ TIM2 PSC/ARR; app dùng khoảng 140077 SPS thay vì requested 140000 để dựng trục thời gian.

### 6.3 Dải đo CH2 và mapping điện áp

- Dải CH2 do người dùng chọn độc lập: 0,3 V / 3,3 V / 10 V.
- Không tự suy dải CH2 từ biên độ DAC vì DUT có thể khuếch đại.
- CH1 Vin luôn dùng đường/calibration trực tiếp.
- CH2 Vout mới dùng calibration theo relay.

Theo resistor thật của AFE, hệ số khôi phục CH2 là:

| Dải | Hệ số |
|---|---:|
| 0,3 V | -0,212766 |
| 3,3 V | -2,127660 |
| 10 V | -6,666667 |

Dấu âm bù tầng U4A đảo. CH2 đi qua tụ C22 nên phần cứng đo AC quanh zero; app có tùy chọn khôi phục DC theo `Vout = gain × Vin`, nhưng ghi rõ đây là DC suy ra, không phải DC đo trực tiếp.

## 7. Cách tạo bộ ảnh thật trong `report/images/result_app/`

### 7.1 Script sử dụng

Script:

```text
app_desktop/_capture_report_tests.py
```

Đây không phải script vẽ ảnh giả. Nó khởi tạo chính `SignalAnalyzerApp`, kết nối COM4 thật, áp cấu hình xuống firmware, chạy live stream rồi chụp widget Qt đang hiển thị.

Quy trình trong script:

1. Tạo `QApplication` với style Fusion.
2. Tạo cửa sổ thật `SignalAnalyzerApp`, kích thước 1600×950 và gọi `show()`.
3. Tìm `COM4`, gọi `toggle_connection()` và kiểm tra pyserial đã mở.
4. Đặt waveform SINE, tần số, amplitude, offset, Fs và relay range.
5. Gửi `apply_range_config()` rồi `apply_device_config()` xuống STM32.
6. Gọi `toggle_live("ANALYZER")` để process reader nhận stream thật.
7. Chờ 3 giây để waveform/history ổn định.
8. Chuyển tab waveform và dùng `window.grab().save(..., "PNG")`.
9. Chuyển tab kết quả, chờ event Qt rồi dùng `window.grab().save()` lần thứ hai.
10. Ghi metadata gồm cấu hình, requested/actual Fs, trạng thái communication và trạng thái DC CH2.
11. Stop stream, chờ COM được app khôi phục rồi mới chạy bài tiếp theo.

### 7.2 Ma trận test

Nhóm quét tần số dùng center 2,0 V, amplitude ±1,0 V, range CH2 3,3 V:

- 100 Hz.
- 1 kHz.
- 5 kHz.
- 10 kHz.
- 20 kHz.

Nhóm amplitude/range ở 1 kHz:

- Center 1,65 V, amplitude ±1,0 V, range 10 V.
- Center 1,0 V, amplitude ±0,5 V, range 10 V.
- Center 0,15 V, amplitude ±0,05 V, range 0,3 V.
- Center 0,5 V, amplitude ±0,5 V, range 3,3 V.

### 7.3 Cách chạy lại

Đóng mọi app/script khác đang giữ COM4. Từ root repository:

```powershell
py -3.12 app_desktop/_capture_report_tests.py 0
py -3.12 app_desktop/_capture_report_tests.py 1
py -3.12 app_desktop/_capture_report_tests.py 2
py -3.12 app_desktop/_capture_report_tests.py 3
py -3.12 app_desktop/_capture_report_tests.py 4
py -3.12 app_desktop/_capture_report_tests.py 5
py -3.12 app_desktop/_capture_report_tests.py 6
py -3.12 app_desktop/_capture_report_tests.py 7
py -3.12 app_desktop/_capture_report_tests.py 8
```

Chạy theo index tạo một cặp ảnh và một file metadata riêng. Có thể bỏ index để script chạy toàn bộ ma trận trong một lần, khi đó script ghi `manifest.json`.

Output của mỗi test:

```text
<id>_waveform.png
<id>_results.png
<id>_metadata.json
```

Ví dụ:

```text
report/images/result_app/01_freq_100hz_waveform.png
report/images/result_app/01_freq_100hz_results.png
report/images/result_app/01_freq_100hz_metadata.json
```

Metadata xác nhận:

- Hardware: STM32F103 + COM4.
- Requested Fs: 140000 SPS.
- Displayed/actual Fs: khoảng 140077 SPS.
- `communication_ok: true`.
- Tên đúng của hai ảnh vừa chụp.

Commit chứa script và toàn bộ ma trận ảnh: `d566ed5 test: capture real hardware app report matrix`.

## 8. Cập nhật báo cáo trong session

`report/report.tex` và `report/report.pdf` đã được cập nhật để:

- Thay ảnh simulation cũ bằng ảnh ứng dụng chạy phần cứng thật.
- Chọn ba ca tần số đại diện: 100 Hz, 5 kHz và 20 kHz.
- Chọn ba ca amplitude/range thể hiện clipping, tín hiệu nhỏ/nhiễu và ADC saturation.
- Thêm ảnh oscilloscope thật: vàng là đầu ra DAC, tím là đầu ra DUT.
- Nêu rõ ADC thực tế 140077 SPS và giới hạn khoảng 7 mẫu/chu kỳ tại 20 kHz.
- Bổ sung hướng nâng cấp STM32H743ZI để hướng đến ít nhất 500 kSPS và spec 1% tại 20 kHz.

Commit báo cáo: `5afe17b update report`.

## 9. Build, nạp và kiểm tra cơ bản

Build/nạp firmware production:

```powershell
cd amplifier_analyzer_fw
pio run -e production
pio run -e production --target upload
```

Sau reset phải đợi COM4 enumerate lại. Nếu chạy script trực tiếp, đóng app desktop trước để tránh hai process cùng mở COM.

Kiểm tra Python:

```powershell
py -3.12 -m py_compile app_desktop/signal_analyzer.py app_desktop/stream_reader_process.py app_desktop/_capture_report_tests.py
py -3.12 -m unittest app_desktop/test_signal_analysis.py
```

Build báo cáo:

```powershell
cd report
cmd /c build.bat
```

## 10. Các giới hạn còn lại và hướng tiếp theo

1. Production giữ 140 kSPS; 145 kSPS mới chỉ sạch trong test ngắn, chưa qualify soak dài.
2. USB CDC FS single-buffer và CPU pack/transport là nút thắt end-to-end hiện tại.
3. 20 kHz tại 140077 SPS chỉ có khoảng 7 mẫu/chu kỳ; đủ Nyquist nhưng chưa đủ tốt cho peak/phase chính xác 1%.
4. MCP4822 ở 200 ksample/s chỉ còn khoảng 0,5 µs settling margin.
5. CH2 đo AC qua C22; DC hiển thị tùy chọn là giá trị suy ra.
6. Cần calibration đa điểm theo range, biên độ và tần số bằng thiết bị chuẩn.
7. Nếu cần đạt spec 1% tại 20 kHz, mục tiêu hợp lý là tối thiểu khoảng 500 kSPS, ADC/DAC nhanh hơn và MCU có dư địa lớn hơn như STM32H743ZI.
8. Muốn vượt 140--150 kSPS lossless trên thiết kế hiện tại cần refactor USB double-buffer/state machine, không chỉ tăng SPI clock.

## 11. Chuỗi commit chính của session

```text
8efc6ca feat: add stable continuous ADC streaming
8353c5e perf: raise stable stream rate to 55 kSPS
b177877 perf: raise stable stream rate to 65 kSPS
f46526d perf: raise stable stream rate to 75 kSPS
1eeef9c perf: raise stable stream rate to 85 kSPS
7891bb3 perf: raise stable stream rate to 95 kSPS
82624f7 feat: qualify 100 kSPS continuous streaming
26408b0 perf: raise stable stream rate to 110 kSPS
893642f perf: raise stable stream rate to 120 kSPS
645a413 perf: raise stable stream rate to 130 kSPS
104a326 perf: raise stable stream rate to 140 kSPS
1144fed perf: optimize packed stream headroom
ea11f00 perf: raise DAC DMA rate to 200 kSPS
2f357ad fix: keep 140 kSPS app stream responsive
0b1562d fix: isolate live USB reader from GUI rendering
6536a3d fix: make DUT input range explicitly manual
16e6635 fix: preserve sample timing in live plot decimation
6a61d63 fix: isolate direct Vin from DUT range scaling
8420ee6 fix: correct DUT range voltage scale mapping
000f791 fix: compensate inverted AC-coupled DUT input
8a1968a fix: derive DUT ranges from analog feedback network
fb8a1c5 fix: render live samples at uniform time intervals
65f8269 feat: reconstruct optional DUT output DC level
d566ed5 test: capture real hardware app report matrix
5afe17b update report
```

## 12. Kết luận bàn giao

Session đã chuyển hệ thống từ một capture blocking khoảng vài chục kSPS và app ghép block giả liên tục sang một pipeline ADC timer/SPI/DMA streaming thật, có sequence và kiểm tra mất mẫu. Tốc độ production đã được nâng theo checkpoint từ 30 lên 140 kSPS, có soak test phần cứng thật. DAC được chuyển khỏi ISR theo từng mẫu sang timer + DMA và chạy tối đa 200 ksample/s mà không phá ADC 140 kSPS.

Phần desktop đã được tách reader sang process riêng, sửa decimation/timestamp và khóa mapping/range đúng theo schematic. Cuối cùng, một script PyQt điều khiển chính app production qua COM4 đã chạy chín bài test và chụp trực tiếp waveform + bảng kết quả, kèm metadata truy vết. Các ảnh trong `report/images/result_app/` vì vậy là ảnh phần cứng thật, không phải ảnh được vẽ hoặc tạo giả.
