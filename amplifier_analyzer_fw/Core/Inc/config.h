#ifndef CONFIG_H
#define CONFIG_H

/**
 * @brief Định nghĩa các chế độ hoạt động (Operating Modes) của dự án.
 * Chỉ kích hoạt duy nhất một chế độ bằng cách gán cho macro ACTIVE_MODE.
 */
#define MODE_NORMAL            0  // Chế độ chạy bình thường (Nhận lệnh từ PC qua USB, đo đạc và phản hồi)
#define MODE_TEST_USB          1  // USB CDC command protocol + simulated sine data
#define MODE_TEST_DAC          2  // Chế độ test DAC (Phát liên tục sóng Sine hoặc mức áp cố định ra MCP4822 để đo dao động ký)
#define MODE_TEST_ADC          3  // Chế độ test ADC (Đọc liên tục điện áp từ ADS7861 và truyền thô lên PC để kiểm tra độ nhiễu)
#define MODE_TEST_SPI_LOOPBACK 4  // Chế độ test SPI ngoại vi (Kiểm tra xem phần cứng SPI có chạy đúng không)
#define MODE_TEST_CALIB_FLASH  5  // Chế độ test đọc/ghi hệ số hiệu chuẩn vào bộ nhớ Flash

/**
 * @brief Chọn CHẾ ĐỘ hoạt động hiện tại cho toàn bộ dự án ở đây.
 * Thay đổi giá trị này để chuyển đổi chế độ làm việc.
 */
#ifndef ACTIVE_MODE
#define ACTIVE_MODE            MODE_NORMAL
#endif

/**
 * @brief Cấu hình thông số phụ trợ cho các chế độ Test
 */
#if (ACTIVE_MODE == MODE_TEST_DAC)
  #define TEST_DAC_FREQUENCY   1000   // Tần số sóng Sine dùng để test DAC (Hz)
  #define TEST_DAC_AMPLITUDE   1000   // Biên độ áp test DAC (mV)
  #define TEST_DAC_GAIN        1      // Hệ số khuếch đại DAC (1: X1, 2: X2)
#endif

#if (ACTIVE_MODE == MODE_TEST_ADC)
  #define TEST_ADC_SAMPLING_RATE 10000 // Tần số lấy mẫu khi test ADC (Hz)
#endif

/**
 * @brief Các cấu hình phần cứng khác
 */
#define DAC_SETTLING_DELAY_CYCLES  40   // Số chu kỳ delay rỗng chờ DAC ổn định điện áp (~4.5 us)

#endif /* CONFIG_H */
