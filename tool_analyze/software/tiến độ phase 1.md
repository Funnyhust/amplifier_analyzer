# BÁO CÁO TIẾN ĐỘ - GIAI ĐOẠN 1 (SOFTWARE)
**Hạng mục:** Tinh chỉnh & Hoàn thiện Phần mềm PC (Python)

*Đánh giá chung: Giai đoạn này đã làm rất tốt bằng dữ liệu giả lập, giờ chỉ cần điều chỉnh để chuẩn bị đón dữ liệu vật lý truyền lên từ STM32.*

### Các công việc ĐÃ HOÀN THÀNH:
- [x] **Xây dựng kiến trúc GUI**: Đã tích hợp thành công cục bộ 2 chế độ trên cùng một giao diện gồm: Single Tone (Oscilloscope) và Sweep Bode.
- [x] **Xây dựng DSP Core**: Cấu trúc thành công và hoàn thiện các thuật toán toán học cốt lõi như tính Gain, độ lệch pha (Phase Cross-correlation), phân tích FFT và THD.

### Các công việc CÒN LẠI (Sắp tới):
- [ ] **Thay thế Nguồn dữ liệu (Data Source)**:
  - Xóa bỏ các hàm tạo dữ liệu ảo (như `generate_signals()`).
  - Tích hợp thư viện `pyserial` để đọc luồng byte từ cổng COM ảo của STM32 thay thế cho thuật toán tự sinh data hiện hành.
- [ ] **Tối ưu hóa Buffer**: Xử lý hàng đợi (Queue hoặc Threading) trên Python để đảm bảo phần mềm có thể nhận một khối lượng lớn dữ liệu tốc độ cao mà không bị tràn bộ nhớ hay gây giật lag giao diện người dùng.
- [ ] **Tính năng Xuất dữ liệu (Export Data)**: Bổ sung module lưu trữ tự động, xuất toàn bộ kết quả quét (Bao gồm mảng Tần số, Gain, Phase) ra các file `.csv` hoặc `.excel` chuẩn chỉ để minh chứng thực nghiệm và xuất biểu đồ trên các phần mềm khác khi cần làm báo cáo tốt nghiệp.
