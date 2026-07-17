/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "usb_device.h"
#include "command_parser.h"
#include "test_controller.h"
#include "mcp4822.h"
#include "ads7861.h"
#include "adc_stream.h"
#include "config.h"
#include "usbd_cdc_if.h"
#include <math.h>
#include <stdio.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN PV */
SPI_HandleTypeDef hspi1;
SPI_HandleTypeDef hspi2;
ads7861_t g_ads7861;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void USB_ForceReenumeration(void);
/* USER CODE BEGIN PFP */
#if (ACTIVE_MODE != MODE_TEST_USB)
static void MX_SPI1_Init(void);
#if (ACTIVE_MODE != MODE_TEST_DAC)
static void MX_SPI2_Init(void);
#endif
#endif
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  /* USER CODE BEGIN 2 */
#if (ACTIVE_MODE != MODE_TEST_USB)
  MX_SPI1_Init();
#if (ACTIVE_MODE != MODE_TEST_DAC)
  MX_SPI2_Init();
#endif
#endif
  USB_ForceReenumeration();
  MX_USB_DEVICE_Init();
  
  test_controller_init();
  command_parser_init();
#if (ACTIVE_MODE != MODE_TEST_USB)
  mcp4822_init();
#if (ACTIVE_MODE != MODE_TEST_DAC)
  if (ads7861_init(&g_ads7861, &hspi2,
                   GPIOB, GPIO_PIN_12,
                   GPIOA, GPIO_PIN_8,
                   GPIOB, GPIO_PIN_10,
                   GPIOB, GPIO_PIN_1,
                   GPIOB, GPIO_PIN_0,
                   GPIOB, GPIO_PIN_11,
                   GPIOB, GPIO_PIN_13,
                   GPIOB, GPIO_PIN_14) != ADS7861_OK ||
      ads7861_self_test_parse() != ADS7861_OK) {
    Error_Handler();
  }
  adc_stream_init(&g_ads7861);
#endif
#endif
  /* USER CODE END 2 */
  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    /* USB ISR only queues complete lines; commands execute in thread context. */
    command_parser_process();
    adc_stream_usb_service();
    test_controller_service();

#if (ACTIVE_MODE == MODE_TEST_DAC)
    /*
     * MCP4822-only bring-up: 50 Hz, 20-point continuous sine on VOUTA.
     * X2 transfer is ideally 1 mV/code, so codes 1350..1950 produce a
     * 1.65 V center with 0.30 V peak. No ADC or calibration is involved.
     */
    static const uint16_t sine_codes[TEST_DAC_POINTS_PER_CYCLE] = {
        1650U, 1743U, 1826U, 1893U, 1935U,
        1950U, 1935U, 1893U, 1826U, 1743U,
        1650U, 1557U, 1474U, 1407U, 1365U,
        1350U, 1365U, 1407U, 1474U, 1557U
    };
    static uint32_t last_update_ms = 0U;
    static uint8_t sample_index = 0U;
    uint32_t now_ms = HAL_GetTick();

    if (now_ms != last_update_ms) {
        last_update_ms = now_ms;
        (void)mcp4822_write_raw(MCP4822_CHANNEL_A, MCP4822_GAIN_X2,
                                sine_codes[sample_index]);
        sample_index++;
        if (sample_index >= TEST_DAC_POINTS_PER_CYCLE) sample_index = 0U;
    }

#elif (ACTIVE_MODE == MODE_TEST_ADC)
    // Chế độ test ADC liên tục: đọc áp từ ADS7861 rồi truyền lên PC qua USB
    ads7861_sample_pair_t sample;
    ads7861_status_t adc_status = ads7861_read_pair(
        &g_ads7861, ADS7861_PAIR_0, &sample);
    
    char msg[64];
    int len = snprintf(msg, sizeof(msg),
                       "ADS:%d A:%d B:%d VALID:%u\r\n",
                       (int)adc_status, (int)sample.ch_a_raw,
                       (int)sample.ch_b_raw, sample.valid);
    
    // Gửi lên PC qua cổng COM ảo
    CDC_Transmit_FS((uint8_t*)msg, len);
    HAL_Delay(200); // Đọc và gửi mỗi 200ms

#elif (ACTIVE_MODE == MODE_TEST_SPI_LOOPBACK)
    // Chế độ test giao tiếp SPI ngoại vi cơ bản
    // Bạn có thể viết thêm logic gửi/nhận SPI để đo xung trên chân logic analyzer
    HAL_Delay(1000);

#elif (ACTIVE_MODE == MODE_TEST_CALIB_FLASH)
    // Chế độ test đọc/ghi hệ số hiệu chuẩn vào Flash
    static uint8_t test_done = 0;
    if (!test_done) {
        char msg[128];
        int len = snprintf(msg, sizeof(msg), "\r\n--- TEST CALIB FLASH ---\r\n");
        CDC_Transmit_FS((uint8_t*)msg, len);
        HAL_Delay(100);
        
        // Reset calib về mặc định
        calibration_reset();
        len = snprintf(msg, sizeof(msg), "Sau khi reset: dac_a=%f, dac_b=%f\r\n", calib_coeffs.dac_a, calib_coeffs.dac_b);
        CDC_Transmit_FS((uint8_t*)msg, len);
        HAL_Delay(100);
        
        // Thay đổi giá trị giả lập
        calib_coeffs.dac_a = 1.234f;
        calib_coeffs.dac_b = -10.5f;
        
        // Lưu xuống flash
        HAL_StatusTypeDef status = calibration_save();
        len = snprintf(msg, sizeof(msg), "Lưu Flash status: %d\r\n", status);
        CDC_Transmit_FS((uint8_t*)msg, len);
        HAL_Delay(100);
        
        // Đọc lại từ flash
        calibration_init();
        len = snprintf(msg, sizeof(msg), "Đọc lại từ Flash: dac_a=%f, dac_b=%f\r\n", calib_coeffs.dac_a, calib_coeffs.dac_b);
        CDC_Transmit_FS((uint8_t*)msg, len);
        
        test_done = 1;
    }
    HAL_Delay(1000);

#elif (ACTIVE_MODE == MODE_TEST_USB)
    /* CDC simulator is command-driven; keep the main loop responsive. */
    HAL_Delay(1);

#else
    // MODE_NORMAL: Chạy bình thường (chờ lệnh USB và chạy theo ngắt)
#endif
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_PeriphCLKInitTypeDef PeriphClkInit = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
  PeriphClkInit.PeriphClockSelection = RCC_PERIPHCLK_USB;
  PeriphClkInit.UsbClockSelection = RCC_USBCLKSOURCE_PLL_DIV1_5;
  if (HAL_RCCEx_PeriphCLKConfig(&PeriphClkInit) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3|GPIO_PIN_8|GPIO_PIN_15, GPIO_PIN_RESET);

  /* PA4 is the software-controlled MCP4822 chip select (inactive high). */
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_4, GPIO_PIN_SET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0|GPIO_PIN_1|GPIO_PIN_3|GPIO_PIN_4,
                    GPIO_PIN_RESET);
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_11|GPIO_PIN_12, GPIO_PIN_SET);

  /*Configure GPIO pins : PA3 PA8 PA15 */
  GPIO_InitStruct.Pin = GPIO_PIN_3|GPIO_PIN_8|GPIO_PIN_15;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /*Configure GPIO pin : PA4 (MCP4822 CS/NSS1) */
  GPIO_InitStruct.Pin = GPIO_PIN_4;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /*Configure GPIO pins : PA5 PA7 (SPI1 SCK/MOSI) */
  GPIO_InitStruct.Pin = GPIO_PIN_5|GPIO_PIN_7;
  GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /*Configure GPIO pins : PB0 PB1 PB11 PB3
                           PB4 */
  GPIO_InitStruct.Pin = GPIO_PIN_0|GPIO_PIN_1|GPIO_PIN_11|GPIO_PIN_3
                          |GPIO_PIN_4;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /*Configure GPIO pin : PB10 */
  GPIO_InitStruct.Pin = GPIO_PIN_10;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /*Configure GPIO pin : PB12 (ADS7861 CS2) */
  GPIO_InitStruct.Pin = GPIO_PIN_12;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /*Configure GPIO pin : PB13 (SPI2 SCK) */
  GPIO_InitStruct.Pin = GPIO_PIN_13;
  GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /*Configure GPIO pin : PB14 (SPI2 MISO/SDA) */
  GPIO_InitStruct.Pin = GPIO_PIN_14;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
static void USB_ForceReenumeration(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};

  __HAL_RCC_GPIOA_CLK_ENABLE();
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_12, GPIO_PIN_RESET);
  GPIO_InitStruct.Pin = GPIO_PIN_12;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /* Override the external D+ pull-up long enough for a real host disconnect. */
  HAL_Delay(150U);
  HAL_GPIO_DeInit(GPIOA, GPIO_PIN_12);
}

#if (ACTIVE_MODE != MODE_TEST_USB)
static void MX_SPI1_Init(void)
{
  hspi1.Instance = SPI1;
  hspi1.Init.Mode = SPI_MODE_MASTER;
  hspi1.Init.Direction = SPI_DIRECTION_1LINE;
  hspi1.Init.DataSize = SPI_DATASIZE_16BIT;
  hspi1.Init.CLKPolarity = SPI_POLARITY_LOW;
  hspi1.Init.CLKPhase = SPI_PHASE_1EDGE;
  hspi1.Init.NSS = SPI_NSS_SOFT;
  /* 18 MHz: a 16-bit DAC frame takes < 1 us at a 200 kSPS update rate. */
  hspi1.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_4;
  hspi1.Init.FirstBit = SPI_FIRSTBIT_MSB;
  hspi1.Init.TIMode = SPI_TIMODE_DISABLE;
  hspi1.Init.CRCCalculation = SPI_CRCCALCULATION_DISABLE;
  hspi1.Init.CRCPolynomial = 10;
  if (HAL_SPI_Init(&hspi1) != HAL_OK)
  {
    Error_Handler();
  }
}

#if (ACTIVE_MODE != MODE_TEST_DAC)
static void MX_SPI2_Init(void)
{
  hspi2.Instance = SPI2;
  hspi2.Init.Mode = SPI_MODE_MASTER;
  hspi2.Init.Direction = SPI_DIRECTION_2LINES;
  hspi2.Init.DataSize = SPI_DATASIZE_8BIT;
  hspi2.Init.CLKPolarity = SPI_POLARITY_LOW;
  /* ADS7861 serial data is valid on the falling clock edge. */
  hspi2.Init.CLKPhase = SPI_PHASE_2EDGE;
  hspi2.Init.NSS = SPI_NSS_SOFT;
  /* APB1=36 MHz, /2 = 18 MHz. Qualified by strict ADS7861 frame stress. */
  hspi2.Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_2;
  hspi2.Init.FirstBit = SPI_FIRSTBIT_MSB;
  hspi2.Init.TIMode = SPI_TIMODE_DISABLE;
  hspi2.Init.CRCCalculation = SPI_CRCCALCULATION_DISABLE;
  hspi2.Init.CRCPolynomial = 10;
  if (HAL_SPI_Init(&hspi2) != HAL_OK)
  {
    Error_Handler();
  }
}
#endif
#endif
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
