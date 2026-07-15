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
  #define TEST_DAC_FREQUENCY_HZ       50U
  #define TEST_DAC_UPDATE_RATE_HZ     1000U
  #define TEST_DAC_POINTS_PER_CYCLE   20U
  #define TEST_DAC_CENTER_CODE        1650U
  #define TEST_DAC_AMPLITUDE_CODE     300U
#endif

#if (ACTIVE_MODE == MODE_TEST_ADC)
  #define TEST_ADC_SAMPLING_RATE 10000 // Tần số lấy mẫu khi test ADC (Hz)
#endif

/**
 * @brief Các cấu hình phần cứng khác
 */
#define DAC_SETTLING_DELAY_CYCLES  40   // Số chu kỳ delay rỗng chờ DAC ổn định điện áp (~4.5 us)

/*
 * The TX analog stage subtracts this bias from the unipolar MCP4822 output.
 * Signal amplitude/offset received from the PC are expressed after that
 * subtraction. Set to 0 only if the DAC is exposed as a unipolar output.
 */
#define DAC_OUTPUT_BIAS_MV          1650.0f

/* ADS7861 internal reference; signed differential span is -VREF..+VREF. */
#define ADS7861_VREF_MV             2500.0f

#endif /* CONFIG_H */
