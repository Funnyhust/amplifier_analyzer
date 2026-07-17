#include "calibration.h"
#include "config.h"
#if defined(STM32F103xB)
#include "stm32f1xx_hal.h"
#elif defined(STM32F407xx)
#include "stm32f4xx_hal.h"
#endif
#include <string.h>
#include <stdio.h>
#include <math.h>

CalibCoeffs_t calib_coeffs;

#if defined(STM32F103xB)
#define FLASH_STORAGE_ADDR   0x0800FC00U // Page 63 (last 1KB page of 64KB)
#elif defined(STM32F407xx)
#define FLASH_SECTOR_ID     FLASH_SECTOR_7
#define FLASH_STORAGE_ADDR   0x08060000U
#endif

void calibration_reset(void) {
    calib_coeffs.dac_a = 1.0f;
    calib_coeffs.dac_b = 0.0f;
    
    /* Vin/ADC1 is a direct path; indices 1/2 remain only for flash ABI. */
    calib_coeffs.adc1_m[0] = 1.0f;
    calib_coeffs.adc1_m[1] = 1.0f;
    calib_coeffs.adc1_m[2] = 1.0f;
    
    calib_coeffs.adc2_m[0] = 1.0f;
    calib_coeffs.adc2_m[1] = 10.0f;
    calib_coeffs.adc2_m[2] = 100.0f;
    
    for (int i = 0; i < 3; i++) {
        calib_coeffs.adc1_c[i] = 0.0f;
        calib_coeffs.adc2_c[i] = 0.0f;
    }
}

void calibration_init(void) {
    // Load from Flash
    CalibCoeffs_t *flash_ptr = (CalibCoeffs_t *)FLASH_STORAGE_ADDR;
    
    // Check if flash contains valid data (not blank 0xFFFFFFFF)
    uint32_t *check_ptr = (uint32_t *)flash_ptr;
    if (*check_ptr == 0xFFFFFFFFU) {
        calibration_reset();
    } else {
        memcpy(&calib_coeffs, flash_ptr, sizeof(CalibCoeffs_t));
    }
}

void calibration_set(const char *key, float val) {
    if (strcmp(key, "dac_x2_a") == 0 || strcmp(key, "dac_a") == 0) {
        calib_coeffs.dac_a = val;
    } else if (strcmp(key, "dac_x2_b") == 0 || strcmp(key, "dac_b") == 0) {
        calib_coeffs.dac_b = val;
    } else if (strcmp(key, "adc1_r0_m") == 0) {
        calib_coeffs.adc1_m[0] = val;
    } else if (strcmp(key, "adc1_r0_c") == 0) {
        calib_coeffs.adc1_c[0] = val;
    } else if (strcmp(key, "adc1_r1_m") == 0) {
        calib_coeffs.adc1_m[1] = val;
    } else if (strcmp(key, "adc1_r1_c") == 0) {
        calib_coeffs.adc1_c[1] = val;
    } else if (strcmp(key, "adc1_r2_m") == 0) {
        calib_coeffs.adc1_m[2] = val;
    } else if (strcmp(key, "adc1_r2_c") == 0) {
        calib_coeffs.adc1_c[2] = val;
    } else if (strcmp(key, "adc2_r0_m") == 0) {
        calib_coeffs.adc2_m[0] = val;
    } else if (strcmp(key, "adc2_r0_c") == 0) {
        calib_coeffs.adc2_c[0] = val;
    } else if (strcmp(key, "adc2_r1_m") == 0) {
        calib_coeffs.adc2_m[1] = val;
    } else if (strcmp(key, "adc2_r1_c") == 0) {
        calib_coeffs.adc2_c[1] = val;
    } else if (strcmp(key, "adc2_r2_m") == 0) {
        calib_coeffs.adc2_m[2] = val;
    } else if (strcmp(key, "adc2_r2_c") == 0) {
        calib_coeffs.adc2_c[2] = val;
    }
}

float calibration_get(const char *key) {
    if (strcmp(key, "dac_x2_a") == 0 || strcmp(key, "dac_a") == 0) {
        return calib_coeffs.dac_a;
    } else if (strcmp(key, "dac_x2_b") == 0 || strcmp(key, "dac_b") == 0) {
        return calib_coeffs.dac_b;
    } else if (strcmp(key, "adc1_r0_m") == 0) {
        return calib_coeffs.adc1_m[0];
    } else if (strcmp(key, "adc1_r0_c") == 0) {
        return calib_coeffs.adc1_c[0];
    } else if (strcmp(key, "adc1_r1_m") == 0) {
        return calib_coeffs.adc1_m[1];
    } else if (strcmp(key, "adc1_r1_c") == 0) {
        return calib_coeffs.adc1_c[1];
    } else if (strcmp(key, "adc1_r2_m") == 0) {
        return calib_coeffs.adc1_m[2];
    } else if (strcmp(key, "adc1_r2_c") == 0) {
        return calib_coeffs.adc1_c[2];
    } else if (strcmp(key, "adc2_r0_m") == 0) {
        return calib_coeffs.adc2_m[0];
    } else if (strcmp(key, "adc2_r0_c") == 0) {
        return calib_coeffs.adc2_c[0];
    } else if (strcmp(key, "adc2_r1_m") == 0) {
        return calib_coeffs.adc2_m[1];
    } else if (strcmp(key, "adc2_r1_c") == 0) {
        return calib_coeffs.adc2_c[1];
    } else if (strcmp(key, "adc2_r2_m") == 0) {
        return calib_coeffs.adc2_m[2];
    } else if (strcmp(key, "adc2_r2_c") == 0) {
        return calib_coeffs.adc2_c[2];
    }
    return 0.0f;
}

void calibration_save(void) {
    HAL_FLASH_Unlock();
    
#if defined(STM32F103xB)
    // Page erase for STM32F103
    FLASH_EraseInitTypeDef EraseInitStruct;
    uint32_t PageError = 0;
    EraseInitStruct.TypeErase = FLASH_TYPEERASE_PAGES;
    EraseInitStruct.PageAddress = FLASH_STORAGE_ADDR;
    EraseInitStruct.NbPages = 1;
    
    if (HAL_FLASHEx_Erase(&EraseInitStruct, &PageError) == HAL_OK) {
        uint32_t *src = (uint32_t *)&calib_coeffs;
        uint32_t dest = FLASH_STORAGE_ADDR;
        uint16_t size_words = sizeof(CalibCoeffs_t) / 4;
        if (sizeof(CalibCoeffs_t) % 4 != 0) size_words++;
        
        for (uint16_t i = 0; i < size_words; i++) {
            HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, dest, src[i]);
            dest += 4;
        }
    }
#elif defined(STM32F407xx)
    // Sector erase for STM32F407
    FLASH_EraseInitTypeDef EraseInitStruct;
    uint32_t SectorError = 0;
    EraseInitStruct.TypeErase = FLASH_TYPEERASE_SECTORS;
    EraseInitStruct.VoltageRange = FLASH_VOLTAGE_RANGE_3;
    EraseInitStruct.Sector = FLASH_SECTOR_ID;
    EraseInitStruct.NbSectors = 1;
    
    if (HAL_FLASHEx_Erase(&EraseInitStruct, &SectorError) == HAL_OK) {
        uint32_t *src = (uint32_t *)&calib_coeffs;
        uint32_t dest = FLASH_STORAGE_ADDR;
        uint16_t size_words = sizeof(CalibCoeffs_t) / 4;
        if (sizeof(CalibCoeffs_t) % 4 != 0) size_words++;
        
        for (uint16_t i = 0; i < size_words; i++) {
            HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD, dest, src[i]);
            dest += 4;
        }
    }
#endif
    
    HAL_FLASH_Lock();
}

uint16_t calibration_voltage_to_dac_code(float voltage_mv, uint8_t gain) {
    /* dac_a/dac_b describe the calibrated X2 transfer in millivolts. */
    float a = calib_coeffs.dac_a;
    float b = calib_coeffs.dac_b;
    float gain_scale;

    if (gain == 2U) {
        gain_scale = 1.0f;
    } else if (gain == 1U) {
        /* X1 has half the ideal mV/code of X2. */
        gain_scale = 0.5f;
    } else {
        return 0U;
    }
    if (fabsf(a) < 1.0e-9f) {
        return 0U;
    }

    float target_code = (voltage_mv - b) / (a * gain_scale);
    if (target_code <= 0.0f) return 0U;
    if (target_code >= 4095.0f) return 4095U;

    return (uint16_t)(target_code + 0.5f);
}

float calibration_adc_code_to_voltage(uint16_t code, uint8_t channel, uint8_t range) {
    /*
     * Capture buffers use offset-binary for compatibility with USB framing,
     * while ADS7861 itself outputs signed 12-bit two's complement. Code 2048
     * therefore means zero differential input and one LSB is VREF / 2048.
     */
    int32_t signed_raw = (int32_t)(code & 0x0FFFU) - 2048;
    float v_shifted = ((float)signed_raw / 2048.0f) * ADS7861_VREF_MV;
    
    float m = 1.0f;
    float c = 0.0f;
    
    if (channel == 1) {
        /* Vin is not routed through the CH2 range relays. */
        m = calib_coeffs.adc1_m[0];
        c = calib_coeffs.adc1_c[0];
    } else {
        m = calib_coeffs.adc2_m[range];
        c = calib_coeffs.adc2_c[range];
    }
    
    // Vinput = m * Vshifted + c
    return m * v_shifted + c;
}
