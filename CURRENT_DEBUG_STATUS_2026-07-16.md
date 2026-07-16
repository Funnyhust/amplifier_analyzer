# Trạng thái debug mới nhất — 16/07/2026

Tài liệu này là handoff hiện tại cho toàn bộ chuỗi desktop app → USB CDC →
STM32F103 → MCP4822/ADS7861. Đọc file này trước khi debug tiếp để tránh lặp lại
các thử nghiệm đã hoàn thành.

## 1. Tóm tắt trạng thái

- Desktop app đã chạy được trong `app_desktop/.venv` với Python 3.14.
- Lỗi `START -> TIMEOUT` đã được tìm ra, sửa, nạp và kiểm chứng trên COM6.
- Lỗi JSON do firmware trả `gain_db=-inf` đã được sửa và kiểm chứng.
- USB/protocol hiện ổn định khi DAC TIM3 chạy 200 kHz.
- Đường thẳng trên app không còn được xem là lỗi transport hoặc lỗi zoom.
  Raw ADC thực tế đang gần như cố định/bão hòa và không thay đổi khi quét mức DC
  của DAC.
- Source mới nhất đã bổ sung nút xem chi tiết/khôi phục control và cơ chế tạo
  capture mới cho từng live frame. Source này build/compile thành công nhưng
  **chưa được nạp lên board và chưa được kiểm thử GUI sau thay đổi cuối**.

## 2. Trạng thái board và source khác nhau ở đâu

### Firmware đang nằm trên board

Board hiện dùng production firmware đã có:

- USB IRQ ưu tiên cao hơn TIM3.
- Hoãn bật TIM3 cho tới sau khi response `START` đã truyền xong.
- Chặn interrupt storm nếu SPI1 ISR lỗi.
- `samples` mặc định 128 và có kiểm tra không vượt buffer 512.
- Không phát JSON chứa NaN/Infinity.
- ADS7861 đang chọn cặp `A0/B0`.

Board đã được gửi `STOP` sau thử nghiệm gần nhất, COM6 không bị script giữ.

### Source mới nhất trong workspace

Ngoài các fix đã nạp ở trên, source hiện còn có hai thay đổi mới chưa nạp/test
trên hardware:

1. `START` khi đang RUNNING sẽ dừng DAC stream và tạo capture mới, không ACK rồi
   trả lại buffer cũ.
2. `LiveCaptureWorker` gửi `START` trước mỗi `GET_RESULT/GET_SAMPLES`, do đó mỗi
   frame live dự kiến là một capture mới.

Kiểm tra mới nhất:

```text
PlatformIO production build: PASS
Flash: 49,932 / 65,536 bytes (76.2%)
RAM:    8,968 / 20,480 bytes (43.8%)
Python py_compile signal_analyzer.py + signal_analysis.py: PASS
git diff --check: PASS (chỉ có cảnh báo LF/CRLF)
```

## 3. Nguyên nhân và fix của START timeout

Trong `Core/Src/usbd_conf.c`, USB IRQ từng có priority `7`, trong khi TIM3 DAC
có priority `2`. Trên Cortex-M, số nhỏ hơn là priority cao hơn. Vì vậy comment
"USB cao hơn TIM3" trái với cấu hình thật.

Sau capture, firmware bật TIM3 ở 200 kHz trước khi gửi `OK` cho `START`. TIM3
có thể làm USB CDC không hoàn thành IN transfer, app chờ 5 giây rồi báo TIMEOUT,
và COM từng kẹt cho đến khi reset.

Fix đã thực hiện:

- USB priority đổi thành `1`, TIM3 giữ `2`.
- DAC timer start được defer sang `test_controller_service()`, tức sau khi ACK
  của command đã truyền xong.
- Nếu `mcp4822_write_raw_isr()` lỗi, TIM3 bị tắt ngay.

## 4. Bằng chứng USB/protocol sau fix

Test trực tiếp bằng Python/pyserial trên COM6, cấu hình:

```text
SINE, 20 kHz, amplitude 300 mV, offset 0 mV,
DAC X2, Fs 200 kSPS, 128 samples
```

Kết quả:

- 20/20 chu kỳ `STOP → RANGE → CONFIG → START → RESULT → SAMPLES → PING` pass.
- `START` trả `OK` ổn định sau khoảng 60–64 ms.
- 20/20 response RESULT là JSON parse được.
- 20/20 binary frame đủ 512-byte payload và XOR CRC đúng.
- `PING` trả `OK` trong khi DAC stream đang chạy 200 kHz.
- Test giống live app: một START rồi 30 lần RESULT/SAMPLES liên tiếp:
  30/30 JSON đúng, frame đủ, CRC đúng và PING đúng.
- Bộ đếm quan sát được: `TX_OK=4,195,412`, `TX_ERR=0`.

## 5. Lỗi JSON đã sửa

Khi `rms_out == 0`, code cũ tính `log10(0)` và gửi:

```text
"gain_db":-inf
```

Đây không phải JSON hợp lệ và làm app báo parse error. Fix hiện tại:

- Chỉ tính log gain khi cả input RMS và output RMS lớn hơn ngưỡng.
- Mọi giá trị trước khi format RESULT đều được kiểm tra `isfinite()`.
- Gain không đo được trả `-99.0`, các metric không hữu hạn khác dùng fallback
  hữu hạn.

## 6. Vì sao waveform hiện vẫn là đường thẳng

Raw capture đã được đọc trực tiếp, không qua calibration/app.

### Cặp ADC A0/B0 đang dùng

- CH1: thường 126–128 mẫu nằm đúng code `1024`.
- CH2: chủ yếu code `4092–4095`, đôi khi `2048` ở range 0.3 V.
- Hai raw word cuối điển hình đọc bằng J-Link:

```text
word A = 0x3000
word B = 0x1FF8
```

Payload tương ứng CH1 khoảng `-1.25 V differential`, CH2 gần full-scale
`+2.50 V differential`. Status A/B của word thứ hai cũng chưa đạt strict
framing nhưng đang được `ADS7861_RELAX_FRAME_VALIDATION=1` chấp nhận.

### Thử cặp ADC A1/B1

Đã build/nạp thử tạm thời rồi hoàn nguyên về A0/B0:

- CH1 ổn định quanh code `1053–1054`.
- CH2 ổn định quanh code `3106–3107`.
- Không xuất hiện sine; cặp này nhiều khả năng không phải cặp PCB đang dùng.

### DC sweep để kiểm tra DAC có tới ADC không

Đã phát DC với offset:

```text
-1000, -500, 0, +500, +1000 mV
```

và thử range `0.3V`, `3.3V`, `10V`.

Kết quả: giá trị ADC settled gần như không thay đổi theo mức DAC ở cả A0/B0
và A1/B1. Vì vậy không có bằng chứng tín hiệu MCP4822 hiện đang tới đầu vào
ADS7861. Khả năng còn lại:

- Thiếu đường loop/cáp từ DAC → DUT/input → ADC.
- Front-end analog chưa được cấp nguồn đúng hoặc đang bão hòa.
- Relay/range path không đúng với PCB.
- Sai net/cặp vi sai trên schematic thực tế.
- Timing/status ADS vẫn cần logic analyzer, nhưng payload ổn định khác nhau giữa
  A0/B0 và A1/B1 cho thấy ADC không chỉ trả một bus hoàn toàn floating.

Không được tạo sine giả trong CH1/CH2 để che lỗi này vì sẽ làm app hiển thị dữ
liệu không phải phép đo thật.

## 7. Lưu ý cấu hình app trong ảnh gần nhất

Ảnh app cho thấy `Offset phát = 1.65 V`. Firmware đã tự cộng bias nội
`DAC_OUTPUT_BIAS_MV = 1650 mV`, nên offset app 1.65 V làm DAC có tâm khoảng
3.30 V; sine ±0.30 V sẽ yêu cầu khoảng 3.0–3.6 V. Đây là cấu hình dễ clipping
ở front-end.

Khi test tiếp, dùng trước:

```text
Frequency: 20 kHz
Amplitude: 0.30 V
Offset:    0.00 V
DAC gain:  X2
Fs:        200 kSPS
Samples:   128
Range:     manual 0.3 V hoặc theo schematic thực tế
```

Tuy nhiên offset 0 đã được dùng trong DC/sine test và ADC vẫn không bám DAC,
nên đổi offset chỉ loại bỏ một nguyên nhân clipping, chưa giải quyết đường
analog.

## 8. UI mới nhất

`app_desktop/signal_analyzer.py` hiện có:

- Nút `Detail View` ngay phía trên waveform.
- Khi vào detail view, panel control và tab bar được ẩn.
- Nút đổi thành `Back to Controls`, luôn còn nhìn thấy để quay lại.
- Double-click waveform cũng gọi cùng chế độ detail.
- Worker live yêu cầu một capture mới cho từng frame.

Thay đổi UI đã qua `py_compile` nhưng chưa được mở GUI kiểm thử lần cuối.

## 9. Việc cần làm ngay khi tiếp tục

1. Nạp source production mới nhất:

   ```powershell
   cd D:\Duong\Aplifier_Analyze\amplifier_analyzer_fw
   pio run -e production -t upload
   ```

2. Chạy app đúng venv:

   ```powershell
   cd D:\Duong\Aplifier_Analyze\app_desktop
   .\.venv\Scripts\python.exe .\signal_analyzer.py
   ```

3. Kiểm tra nút `Detail View` và `Back to Controls`.
4. Với oscilloscope/logic analyzer, đo đồng thời:
   - MCP4822 VOUTA.
   - Hai chân vi sai của channel ADS thực sự nối trên PCB.
   - REFIN/REFOUT khoảng 2.5 V.
   - Nguồn analog/digital ADS khoảng 5 V theo datasheet.
   - CS, RD/CONVST, CLOCK, SERIAL DATA A, BUSY.
5. Xác định bằng schematic/layout thật DAC/DUT output đi vào A0/B0 hay A1/B1.
6. Chỉ tắt `ADS7861_RELAX_FRAME_VALIDATION` sau khi xác minh đúng status bit,
   32 clock và thứ tự word trên logic analyzer.

## 10. File source đang thay đổi cho đợt fix này

- `amplifier_analyzer_fw/Core/Src/usbd_conf.c`
- `amplifier_analyzer_fw/Core/Src/test_controller.c`
- `amplifier_analyzer_fw/Core/Inc/test_controller.h`
- `amplifier_analyzer_fw/Core/Src/main.c`
- `amplifier_analyzer_fw/Core/Src/measurement_engine.c`
- `app_desktop/signal_analyzer.py`

`platformio.ini` cũng đang modified vì `debug_speed` là `4000`; thay đổi này đã
có trước đợt fix hiện tại và không được hoàn nguyên.

Repo còn có rất nhiều tracked build artifact, `.venv` và thư mục firmware cũ ở
trạng thái deleted/modified. Không dùng `git reset --hard` hoặc cleanup hàng
loạt vì đó là thay đổi có sẵn của người dùng.

