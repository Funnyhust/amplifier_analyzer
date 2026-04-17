# BẢNG TỔNG HỢP CÔNG VIỆC (FIRMWARE & SOFTWARE)

- **Dự án**: Thiết bị đo đáp ứng tần số (Signal Analyzer & Oscilloscope)
- **Nền tảng phần cứng**: STM32F407VET6
- **Nền tảng phần mềm**: Python (PyQt6 + PyQtGraph + SciPy)

---

## GIAI ĐOẠN 1: SOFTWARE (PHẦN MỀM PC) - Tinh chỉnh & Hoàn thiện

> *Giai đoạn này bạn đã làm rất tốt bằng dữ liệu giả lập, giờ chỉ cần điều chỉnh để chuẩn bị đón dữ liệu thật.*

- [X] **Xây dựng kiến trúc GUI**: Tích hợp 2 chế độ (Single Tone/Oscillo và Sweep Bode) trên cùng một giao diện.
- [X] **Xây dựng DSP Core**: Hoàn thiện các thuật toán toán học (Tính Gain, Phase Cross-correlation, FFT, THD).
- [ ] **Thay thế Nguồn dữ liệu (Data Source)**:
  - Xóa bỏ hàm `generate_signals()` giả lập.
  - Tích hợp thư viện `pyserial` để đọc luồng byte từ cổng COM ảo của STM32.
- [ ] **Tối ưu hóa Buffer**: Xử lý hàng đợi (Queue) trên Python để đảm bảo khi STM32 gửi dữ liệu tốc độ cao không bị tràn bộ nhớ hoặc giật lag giao diện.
- [ ] **Export Data**: Thêm tính năng xuất kết quả quét (mảng Tần số, Gain, Phase) ra file `.csv` hoặc `.excel` để thầy cô dễ nghiệm thu và vẽ lại khi cần.

---

## GIAI ĐOẠN 2: THIẾT KẾ GIAO THỨC (PROTOCOL DESIGN)

> *Đây là "ngôn ngữ chung" để phần mềm Python và chip STM32 hiểu nhau.*

- [ ] **Thiết kế Packet truyền lệnh (PC -> STM32)**: Quy định định dạng lệnh cấu hình. Ví dụ:
  - Bắt đầu quét: `<CMD:START_SWEEP, F_START:100, F_STOP:500K>`
  - Phát 1 tần số: `<CMD:SINGLE, FREQ:1000, AMP:3.3>`
- [ ] **Thiết kế Packet truyền dữ liệu (STM32 -> PC)**: Quy định khung truyền data tốc độ cao. Ví dụ truyền hệ Hex:
  - `[Header 0xAA 0xBB] [Type: OSC/BODE] [Length] [Data_CH1...] [Data_CH2...] [Checksum]`
- [ ] **Viết bộ Parser**: Code hàm đóng gói/giải mã (encode/decode) gói tin trên cả Python và C (STM32).

---

## GIAI ĐOẠN 3: FIRMWARE STM32F407 (LẬP TRÌNH NHÚNG)

> *Đây là phần việc cốt lõi và nặng nhất của bạn trong thời gian tới.*

- [ ] **Cấu hình System Clock**: Setup Clock Tree của STM32F407 chạy ở tần số tối đa (168MHz) để đảm bảo năng lực tính toán và tốc độ lấy mẫu.
- [ ] **Cấu hình USB CDC (Virtual COM)**: Cấu hình ngoại vi USB OTG FS để làm cổng giao tiếp giả lập COM port với máy tính (đảm bảo băng thông lớn hơn UART truyền thống).
- [ ] **Phát triển Khối TX (Signal Generation)**:
  - *Nếu dùng DAC nội + DMA*: Viết thuật toán tạo mảng (Look-up table) sóng Sine và xuất ra chân DAC.
  - *Nếu dùng chip DDS (AD9833)*: Viết driver giao tiếp SPI và hàm điều khiển tần số/pha cho AD9833.
- [ ] **Phát triển Khối RX (Data Acquisition)**:
  - *Cấu hình ADC*: Thiết lập chế độ Simultaneous (Lấy mẫu đồng thời) hoặc Triple Interleaved để đạt tốc độ 2.4 MSPS.
  - *Cấu hình DMA*: Setup DMA Double Buffering (Ping-Pong) chuyển dữ liệu trực tiếp từ ADC vào RAM mà không cần CPU can thiệp.
- [ ] **Đồng bộ hóa TX/RX**: Viết Logic State Machine (Máy trạng thái) để xử lý việc: Nhận lệnh -> Đổi tần số phát -> Chờ mạch phần cứng ổn định -> Bắt đầu thu ADC -> Đẩy lên PC.

---

## GIAI ĐOẠN 4: TÍCH HỢP & HIỆU CHUẨN CÙNG PHẦN CỨNG (HARDWARE INTEGRATION)

> *Làm việc chung với Duy Anh khi mạch phần cứng đã hàn xong.*

- [ ] **Chốt kiến trúc ADC với chip AD8307**:
  - *Cần thảo luận ngay*: Nếu Duy Anh dùng AD8307 chuyển đổi ra DC để tính Gain, bạn cần yêu cầu Duy Anh phải giữ lại đường tín hiệu AC nguyên bản cấp vào 1 kênh ADC khác để bạn còn tính Phase và vẽ FFT.
- [ ] **Test Giao tiếp**: Gắn mạch vào PC, dùng nút "Start Oscillo" trên phần mềm Python để soi raw data xem có bị nhiễu do Ground Loop không.
- [ ] **Hiệu chuẩn (Calibration)**:
  - Đo độ trễ pha gốc của bản thân phần cứng ở các tần số khác nhau.
  - Code thêm các tham số bù trừ (Offset/Multiplier) vào phần mềm Python để khử sai số của hệ thống trước khi hiện kết quả đo của DUT.
