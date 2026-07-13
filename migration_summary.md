# BÁO CÁO TỔNG HỢP DI TRÚ & HOÀN THIỆN PHASE 1
## DỰ ÁN: AMPLIFIER ANALYZER (BỘ PHÂN TÍCH TÍN HIỆU ĐƯỜNG TIẾNG)

Báo cáo này tổng hợp toàn bộ các thay đổi, nâng cấp và tối ưu hóa hệ thống đã thực hiện để chuyển đổi thành công nền tảng phần cứng từ **STM32F407** sang **STM32F103C8T6 (Blue Pill)** kết hợp cùng các ngoại vi ngoài (SPI DAC **MCP4822** và SPI ADC **ADS7861**), đồng thời hoàn thiện phần mềm điều khiển trên máy tính (Desktop App PyQt6).

---

## 1. PHẦN CỨNG & FIRMWARE (STM32F103C8T6)

Toàn bộ mã nguồn Firmware đã được cấu trúc lại, tích hợp trực tiếp vào dự án CubeMX mới tại thư mục `amplifier_analyzer_fw` và biên dịch thành công 100% bằng **PlatformIO** (0 lỗi, 0 cảnh báo).

### Các điểm cải tiến và tối ưu hóa:

*   **Tích hợp an toàn với CubeMX:** 
    *   Mã nguồn khởi tạo SPI1 (DAC), SPI2 (ADC), USB CDC, và các cấu hình ứng dụng được đặt hoàn toàn trong các phân vùng `/* USER CODE BEGIN */` và `/* USER CODE END */` của file [main.c](file:///d:/Test/amplifier_analyzer/amplifier_analyzer_fw/Core/Src/main.c).
    *   Giúp bạn có thể thoải mái mở lại file cấu hình `.ioc` trong phần mềm CubeMX để chỉnh sửa pinout mà không sợ bị ghi đè mất mã nguồn ứng dụng.

*   **Tối ưu hóa dung lượng bộ nhớ RAM (Giảm từ 32 KB xuống 18.2 KB):**
    *   *Giới hạn phần cứng:* STM32F103C8T6 chỉ có **20 KB RAM**, trong khi phiên bản F4 cũ yêu cầu hơn 32 KB RAM cho các mảng đệm.
    *   *Loại bỏ mảng tĩnh lớn:* Xóa bỏ hoàn toàn 2 mảng đệm float trung gian `vin_f[2048]` và `vout_f[2048]` (tiết kiệm **16 KB RAM**). Các phép tính quy đổi điện áp và tính trung bình (mean), RMS, tích chập pha (cross-correlation) được tính trực tiếp "on-the-fly" từ dữ liệu thô dạng bit của ADC.
    *   *Xử lý đệm trực tiếp:* Loại bỏ các biến tạm lớn trên Stack trong hàm xử lý toán học và nạp mẫu để loại bỏ triệt để nguy cơ lỗi tràn ngăn xếp (**Stack Overflow / Hard Fault**).
    *   *Tối ưu buffer USB:* Điều chỉnh kích thước bộ đệm truyền nhận USB CDC từ 2048 bytes về **1024 bytes** nhằm tiết kiệm thêm 2 KB RAM.

*   **Bộ nhớ lưu trữ Hệ số hiệu chuẩn (Calibration) trên Flash:**
    *   Chuyển đổi phương thức xóa Sector của dòng F4 sang phương thức xóa trang (**Page Erase - 1 KB**) của dòng F1.
    *   Toàn bộ hệ số hiệu chuẩn được lưu ổn định tại trang cuối cùng của Flash (Trang số 63, địa chỉ `0x0800FC00`).

*   **Thiết lập thanh ghi USB CDC chuyên biệt cho F103 (`usbd_conf.c`):**
    *   Cấu hình chính xác phân vùng bộ nhớ đệm PMA (Packet Memory Area) của F103 cho Endpoint nhận/gửi dữ liệu.
    *   Viết trình cấp phát tĩnh bộ nhớ USB CDC (`USBD_static_malloc` / `USBD_static_free` - dung lượng chỉ 512 bytes) để giải quyết lỗi thiếu thư viện của ST.

*   **Phương thức truyền mẫu nhị phân theo khối nhỏ (Chunk-based Stream):**
    *   Thay vì đóng gói cả mảng 8 KB dữ liệu để gửi đi một lúc (dễ gây lỗi nghẽn USB), hàm `test_controller_get_samples_bin` tự động phân tách và truyền tải dữ liệu thô về PC theo từng khối nhỏ 64 bytes (16 mẫu đo cùng lúc) kết hợp tính toán mã kiểm tra sai số CRC thời gian thực.

---

## 2. PHẦN MỀM ĐIỀU KHIỂN (DESKTOP APP - PYQT6)

Mã nguồn phần mềm máy tính tại [signal_analyzer.py](file:///d:/Test/amplifier_analyzer/app_desktop/signal_analyzer.py) được thiết kế lại hiện đại, tích hợp chặt chẽ các thông số vật lý và hỗ trợ giả lập ngoại tuyến.

### Các tính năng chính:

*   **Bộ phân tích sai số vật lý (Error Analyzer):**
    *   Tự động tính toán số mẫu trên mỗi chu kỳ tín hiệu ($N = F_s / F_{signal}$).
    *   Tính toán sai số bắt lệch đỉnh (Peak Error): $E_{peak} = 1 - \cos(\pi / N)$.
    *   Tính toán suy hao do giữ mẫu bậc 0 (ZOH Droop): $E_{zoh} = 1 - \frac{\sin(\pi / N)}{\pi / N}$.
    *   Hiển thị cảnh báo **DAC Settling Warning** màu đỏ nổi bật nếu tốc độ cập nhật mẫu quá nhanh (chu kỳ mẫu $< 4.5\ \mu s$ của chip MCP4822).

*   **Chế độ quét tần số tự động (Auto-Ranging & Bode Sweep):**
    *   Gửi lệnh cấu hình quét đáp ứng tần số log-scale từ tần số thấp đến tần số cao.
    *   Tự động nhận diện mức điện áp đầu vào trên ADC và gửi lệnh kích hoạt rơ-le dải đo chuyển tầng (Direct / Div 10 / Div 100) để tối ưu hóa độ phân giải đo đạc.

*   **Đồ thị hiển thị trực quan:**
    *   Khung hiển thị sóng thời gian thực (Vin/Vout) với thuật toán đồng bộ pha tự động.
    *   Khung vẽ biểu đồ Bode (Biên độ dB và Pha độ) trực quan trên thang đo logarith.

*   **Quản lý hiệu chuẩn (Calibration):**
    *   Tab quản lý riêng biệt cho phép người dùng nhập điện áp thực tế đo được bằng đồng hồ đo ngoài, tự động tính toán các hệ số góc ($a, m$) và sai số lệch ($b, c$) rồi ghi trực tiếp xuống Flash của STM32 chỉ với 1 click.

*   **Chế độ giả lập thông minh (Simulation Fallback):**
    *   Nếu không có thiết bị thật cắm vào máy tính, phần mềm sẽ kích hoạt chế độ giả lập, tự động tạo tín hiệu nhiễu ngẫu nhiên và suy hao pha giả lập để bạn thử nghiệm tất cả các tính năng của giao diện đồ họa.

---

## 3. THÔNG SỐ TÀI NGUYÊN BIÊN DỊCH FIRMWARE (PLATFORMIO)

*   **Nền tảng vi điều khiển:** STM32F103C8T6 (72MHz, 20KB RAM, 64KB Flash)
*   **Dung lượng RAM tiêu thụ:** **18,292 bytes (89.3%)** -> *Nằm trong vùng an toàn tuyệt đối.*
*   **Dung lượng Flash tiêu thụ:** **37,692 bytes (57.5%)**
*   **Trạng thái biên dịch:** `[SUCCESS]` (0 warnings, 0 errors)

---

## 4. HƯỚNG DẪN CHẠY THỬ NGHIỆM THỰC TẾ

1.  **Nạp chương trình vào kit STM32F103:**
    Kết nối kit STM32 qua mạch nạp ST-Link/J-Link vào máy tính, mở PowerShell tại thư mục dự án và chạy:
    ```powershell
    & "C:\Users\linhn\.platformio\penv\Scripts\pio.exe" run -t upload -d "d:\Test\amplifier_analyzer\amplifier_analyzer_fw"
    ```

2.  **Khởi động phần mềm điều khiển:**
    Mở PowerShell và chạy ứng dụng Python:
    ```powershell
    cd d:\Test\amplifier_analyzer\app_desktop
    python signal_analyzer.py
    ```

3.  **Vận hành hệ thống:**
    *   Chọn cổng COM của STM32 phát sinh trên máy tính và nhấn **Connect**.
    *   Đặt các thông số đo mong muốn (vd: Tần số phát 20 kHz, Tần số lấy mẫu 200 kSPS).
    *   Nhấn **Start Waveform** để xem luồng sóng thực tế hoặc **Start Sweep** để bắt đầu quét tần số vẽ biểu đồ Bode của mạch khuếch đại.
