#include "command_parser.h"
#include "test_controller.h"
#include "calibration.h"
#include "range_control.h"
#include "mcp4822.h"
#include "ads7861.h"
#include "adc_stream.h"
#include "config.h"
#include "protocol.h"
#include "usbd_cdc_if.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

#define CMD_BUF_SIZE 256
static char cmd_buf[CMD_BUF_SIZE];
static char execute_buf[CMD_BUF_SIZE];
static uint16_t cmd_idx = 0;
static volatile uint8_t pending_ready = 0U;

extern USBD_HandleTypeDef hUsbDeviceFS;
#if defined(STM32F103xB)
extern ads7861_t g_ads7861;
#endif

static void send_response(const char *resp) {
    uint16_t len = strlen(resp);
    protocol_send_raw((uint8_t *)resp, len);
}

static unsigned int test_error_protocol_code(TestError_t error) {
    switch (error) {
        case TEST_ERROR_DAC_SPI:     return 201U;
        case TEST_ERROR_ADC_TIMEOUT: return 202U;
        case TEST_ERROR_ADC_SPI:     return 203U;
        case TEST_ERROR_ADC_FRAME:   return 204U;
        case TEST_ERROR_ADC_MODE:    return 205U;
        case TEST_ERROR_CONFIG_FIELDS:return 102U;
        case TEST_ERROR_DAC_RANGE:   return 103U;
        case TEST_ERROR_NONE:        return 0U;
        default:                     return 299U;
    }
}

void command_parser_init(void) {
    memset(cmd_buf, 0, CMD_BUF_SIZE);
    cmd_idx = 0;
    pending_ready = 0U;
}

void command_parser_feed_char(uint8_t ch) {
    /* One command is processed at a time; host commands are request/response. */
    if (pending_ready) {
        return;
    }

    if (ch == '\r' || ch == '\n') {
        if (cmd_idx > 0) {
            cmd_buf[cmd_idx] = '\0';
            pending_ready = 1U;
        }
    } else {
        if (cmd_idx < CMD_BUF_SIZE - 1) {
            cmd_buf[cmd_idx++] = (char)ch;
        } else {
            // Buffer full, reset
            cmd_idx = 0;
        }
    }
}

void command_parser_process(void) {
    if (!pending_ready) {
        return;
    }

    /*
     * Copy the completed command, then release the USB receive buffer before
     * executing it. The host may send the next request as soon as it receives
     * our response, including while a binary frame is being prepared.
     */
    memcpy(execute_buf, cmd_buf, cmd_idx + 1U);
    cmd_idx = 0U;
    pending_ready = 0U;
    command_parser_execute(execute_buf);
}

static char* get_param_value(char *str, const char *key) {
    size_t key_len = strlen(key);
    char *p = str;

    while ((p = strstr(p, key)) != NULL) {
        uint8_t at_field_start = (p == str || p[-1] == ',') ? 1U : 0U;
        if (at_field_start != 0U && p[key_len] == '=') {
            return p + key_len + 1U;
        }
        p++;
    }
    return NULL;
}

void command_parser_execute(char *cmd_line) {
    // Basic trimming of trailing whitespace
    uint16_t len = strlen(cmd_line);
    while (len > 0 && (cmd_line[len-1] == ' ' || cmd_line[len-1] == '\r' || cmd_line[len-1] == '\n')) {
        cmd_line[--len] = '\0';
    }
    
    if (strcmp(cmd_line, "PING") == 0) {
        send_response("OK\n");
    } 
    else if (strcmp(cmd_line, "INFO") == 0) {
#if (ACTIVE_MODE == MODE_TEST_USB)
        send_response("DATA:Amplifier Analyzer F103 USB CDC SIM v1.0\n");
#elif (ACTIVE_MODE == MODE_TEST_DAC)
        send_response("DATA:Amplifier Analyzer F103 MCP4822 CONTINUOUS TEST\n");
#else
        send_response("DATA:Amplifier Analyzer F103 v1.0\n");
#endif
    } 
    else if (strcmp(cmd_line, "GET_STATUS") == 0) {
        if (current_state == STATE_IDLE) send_response("DATA:IDLE\n");
        else if (current_state == STATE_RUNNING) send_response("DATA:RUNNING\n");
        else if (current_state == STATE_CALIBRATION) send_response("DATA:CALIBRATION\n");
        else send_response("DATA:ERROR\n");
    } 
    else if (strcmp(cmd_line, "GET_RANGE") == 0) {
        char range_buf[64];
        snprintf(range_buf, sizeof(range_buf), "DATA:mode=%s,range=%s\n",
                 range_control_get_mode_name(), range_control_get_range_name());
        send_response(range_buf);
    }
    else if (strncmp(cmd_line, "ADC_STREAM_START:FS=", 20) == 0) {
        uint32_t fs = (uint32_t)strtoul(cmd_line + 20, NULL, 10);
        if (adc_stream_start(fs)) send_response("OK\n");
        else send_response("ERR:302,ADC_STREAM_CONFIG\n");
    }
    else if (strncmp(cmd_line, "ADC_USB_STREAM_START:FS=", 24) == 0) {
        uint32_t fs = (uint32_t)strtoul(cmd_line + 24, NULL, 10);
        if (adc_stream_start(fs)) {
            adc_stream_set_usb_output(1U);
            send_response("OK\n");
        } else {
            send_response("ERR:302,ADC_STREAM_CONFIG\n");
        }
    }
    else if (strcmp(cmd_line, "ADC_STREAM_STOP") == 0) {
        adc_stream_stop();
        send_response("OK\n");
    }
    else if (strcmp(cmd_line, "ADC_STREAM_STATUS") == 0) {
        adc_stream_stats_t stats;
        char out[224];
        adc_stream_get_stats(&stats);
        snprintf(out, sizeof(out),
                 "DATA:RUN=%u,FS=%lu,ACTUAL_FS=%lu,PRODUCED=%lu,OVERRUN=%lu,INVALID=%lu,OVERWRITE=%lu,BUILD_CYC=%lu,SEND_CYC=%lu\n",
                 stats.running, (unsigned long)stats.requested_fs,
                 (unsigned long)stats.actual_fs,
                 (unsigned long)stats.produced,
                 (unsigned long)stats.timer_overrun,
                 (unsigned long)stats.invalid_frame,
                 (unsigned long)stats.ring_overwrite,
                 (unsigned long)stats.usb_build_cycles_max,
                 (unsigned long)stats.usb_send_cycles_max);
        send_response(out);
    }
    else if (strcmp(cmd_line, "DAC_TEST_STATUS") == 0) {
        char dac_buf[128];
        snprintf(dac_buf, sizeof(dac_buf),
                 "DATA:TX_OK=%lu,TX_ERR=%lu,LAST_FRAME=%04X,FREQ_HZ=%u,UPDATE_HZ=%u,RUN=%u\n",
                 (unsigned long)mcp4822_get_tx_ok_count(),
                 (unsigned long)mcp4822_get_tx_error_count(),
                 mcp4822_get_last_frame(),
#if (ACTIVE_MODE == MODE_TEST_DAC)
                 (unsigned int)TEST_DAC_FREQUENCY_HZ,
                 (unsigned int)TEST_DAC_UPDATE_RATE_HZ,
                 1U);
#else
                 (unsigned int)current_config.freq,
                 (unsigned int)test_controller_get_dac_update_hz(),
                 (unsigned int)test_controller_is_dac_stream_running());
#endif
        send_response(dac_buf);
    }
    else if (strcmp(cmd_line, "SET_RANGE:AUTO") == 0) {
        range_control_set_auto();
        send_response("OK\n");
    }
    else if (strcmp(cmd_line, "SET_RANGE:0.3V") == 0) {
        range_control_set_manual(SIGNAL_RANGE_0V3);
        send_response("OK\n");
    }
    else if (strcmp(cmd_line, "SET_RANGE:3.3V") == 0) {
        range_control_set_manual(SIGNAL_RANGE_3V3);
        send_response("OK\n");
    }
    else if (strcmp(cmd_line, "SET_RANGE:10V") == 0) {
        range_control_set_manual(SIGNAL_RANGE_10V);
        send_response("OK\n");
    }
    else if (strncmp(cmd_line, "SET_RANGE:", 10) == 0) {
        send_response("ERR:101,Invalid range; use AUTO,0.3V,3.3V,10V\n");
    }
    else if (strncmp(cmd_line, "CONFIG:", 7) == 0) {
        char *params = cmd_line + 7;
        
        TestConfig_t cfg = current_config; // Start with current config
        
        char *val;
        
        val = get_param_value(params, "WAVE");
        if (val) {
            if (strncmp(val, "SINE", 4) == 0) cfg.wave_type = WAVE_SINE;
            else if (strncmp(val, "SQUARE", 6) == 0) cfg.wave_type = WAVE_SQUARE;
            else if (strncmp(val, "TRIANGLE", 8) == 0) cfg.wave_type = WAVE_TRIANGLE;
            else if (strncmp(val, "DC", 2) == 0) cfg.wave_type = WAVE_DC;
        }
        
        val = get_param_value(params, "FREQ");
        if (val) cfg.freq = atoi(val);
        
        val = get_param_value(params, "AMP_MV");
        if (val) cfg.amp_mv = atoi(val);
        
        val = get_param_value(params, "OFFSET_MV");
        if (val) cfg.offset_mv = atoi(val);
        
        val = get_param_value(params, "DAC_GAIN");
        if (val) {
            if (strncmp(val, "X1", 2) == 0) cfg.dac_gain = 1;
            else if (strncmp(val, "X2", 2) == 0) cfg.dac_gain = 2;
        }
        
        val = get_param_value(params, "FS");
        if (val) cfg.fs = atoi(val);
        
        val = get_param_value(params, "SAMPLES");
        if (val) cfg.samples = atoi(val);
        
        if (test_controller_configure(&cfg)) {
            send_response("OK\n");
        } else {
            char error_buf[80];
            TestError_t error = test_controller_get_last_error();
            snprintf(error_buf, sizeof(error_buf), "ERR:%u,%s\n",
                     test_error_protocol_code(error),
                     test_controller_get_last_error_text());
            send_response(error_buf);
        }
    } 
    else if (strcmp(cmd_line, "START") == 0) {
        if (test_controller_start()) {
            send_response("OK\n");
        } else {
            char error_buf[96];
            TestError_t error = test_controller_get_last_error();
            if (error == TEST_ERROR_ADC_FRAME) {
                uint16_t word_a;
                uint16_t word_b;
                test_controller_get_last_adc_words(&word_a, &word_b);
                snprintf(error_buf, sizeof(error_buf),
                         "ERR:204,ADC_FRAME,W0=%04X,W1=%04X\n",
                         word_a, word_b);
            } else {
                snprintf(error_buf, sizeof(error_buf), "ERR:%u,%s\n",
                         test_error_protocol_code(error),
                         test_controller_get_last_error_text());
            }
            send_response(error_buf);
        }
    } 
    else if (strcmp(cmd_line, "GET_LAST_ERROR") == 0) {
        char error_buf[64];
        snprintf(error_buf, sizeof(error_buf), "DATA:%u,%s\n",
                 test_error_protocol_code(test_controller_get_last_error()),
                 test_controller_get_last_error_text());
        send_response(error_buf);
    }
    else if (strcmp(cmd_line, "ADC_GPIO_DIAG") == 0) {
#if defined(STM32F103xB)
        char gpio_buf[160];
        uint32_t idr = GPIOB->IDR;
        uint32_t odr = GPIOB->ODR;
        snprintf(gpio_buf, sizeof(gpio_buf),
                 "DATA:IDR=%04lX,ODR=%04lX,M0=%lu,A0=%lu,BUSY=%lu,"
                 "M1=%lu,CS=%lu,CLK=%lu,SDO_A=%lu\n",
                 (unsigned long)(idr & 0xFFFFU),
                 (unsigned long)(odr & 0xFFFFU),
                 (unsigned long)((idr >> 0) & 1U),
                 (unsigned long)((idr >> 1) & 1U),
                 (unsigned long)((idr >> 10) & 1U),
                 (unsigned long)((idr >> 11) & 1U),
                 (unsigned long)((idr >> 12) & 1U),
                 (unsigned long)((idr >> 13) & 1U),
                 (unsigned long)((idr >> 14) & 1U));
        send_response(gpio_buf);
#else
        send_response("ERR:301,ADC_GPIO_DIAG_UNSUPPORTED\n");
#endif
    }
    else if (strcmp(cmd_line, "ADC_READ_ONCE") == 0) {
#if defined(STM32F103xB) && (ACTIVE_MODE != MODE_TEST_USB) && \
    (ACTIVE_MODE != MODE_TEST_DAC)
        ads7861_sample_pair_t sample;
        unsigned int busy_before = (unsigned int)HAL_GPIO_ReadPin(
            GPIOB, GPIO_PIN_10);
        ads7861_status_t status = ads7861_read_pair(
            &g_ads7861, ADS7861_PAIR_0, &sample);
        unsigned int busy_after = (unsigned int)HAL_GPIO_ReadPin(
            GPIOB, GPIO_PIN_10);
        unsigned int strict = (unsigned int)(
            ((sample.word_a & 0x0003U) == 0U) &&
            ((sample.word_b & 0x0003U) == 0U) &&
            (sample.status_a == 0U) && (sample.status_b == 1U));
        char adc_buf[192];
        snprintf(adc_buf, sizeof(adc_buf),
                 "DATA:ERR=%u,W0=%04X,W1=%04X,RA=%d,RB=%d,SA=%u,SB=%u,VALID=%u,STRICT=%u,B0=%u,B1=%u\n",
                 (unsigned int)status,
                 sample.word_a, sample.word_b,
                 (int)sample.ch_a_raw, (int)sample.ch_b_raw,
                 (unsigned int)sample.status_a,
                 (unsigned int)sample.status_b,
                 (unsigned int)sample.valid, strict,
                 busy_before, busy_after);
        send_response(adc_buf);
#else
        send_response("ERR:301,ADC_READ_ONCE_UNSUPPORTED\n");
#endif
    }
    else if (strcmp(cmd_line, "ADC_READ_TRIPLE") == 0 ||
             strcmp(cmd_line, "ADC_READ_TRIPLE1") == 0) {
#if defined(STM32F103xB) && (ACTIVE_MODE != MODE_TEST_USB) && \
    (ACTIVE_MODE != MODE_TEST_DAC)
        uint16_t words[3];
        uint8_t ch[3] = {0U, 0U, 0U};
        uint8_t ab[3] = {0U, 0U, 0U};
        ads7861_pair_t pair = (strcmp(cmd_line, "ADC_READ_TRIPLE1") == 0)
                                ? ADS7861_PAIR_1 : ADS7861_PAIR_0;
        ads7861_status_t status = ads7861_debug_read_triplet(
            &g_ads7861, pair, words);
        for (uint8_t i = 0U; i < 3U; i++) {
            (void)ads7861_parse_word(words[i], &ch[i], &ab[i]);
        }
        char adc_buf[64];
        snprintf(adc_buf, sizeof(adc_buf),
                 "DATA:E=%u,W=%04X,%04X,%04X,S=%u,%u,%u\n",
                 (unsigned int)status,
                 words[0], words[1], words[2],
                 (unsigned int)((ch[0] << 1) | ab[0]),
                 (unsigned int)((ch[1] << 1) | ab[1]),
                 (unsigned int)((ch[2] << 1) | ab[2]));
        send_response(adc_buf);
#else
        send_response("ERR:301,ADC_READ_TRIPLE_UNSUPPORTED\n");
#endif
    }
    else if (strcmp(cmd_line, "ADC_BUSY_TRACE") == 0) {
#if defined(STM32F103xB) && (ACTIVE_MODE != MODE_TEST_USB) && \
    (ACTIVE_MODE != MODE_TEST_DAC)
        uint16_t word = 0U;
        uint16_t busy_mask = 0U;
        uint8_t busy_before = 0U;
        uint8_t busy_after_start = 0U;
        uint8_t busy_after_word = 0U;
        ads7861_status_t status = ads7861_debug_busy_trace(
            &g_ads7861, ADS7861_PAIR_0, &word, &busy_mask,
            &busy_before, &busy_after_start, &busy_after_word);
        char adc_buf[96];
        snprintf(adc_buf, sizeof(adc_buf),
                 "DATA:E=%u,W=%04X,BM=%04X,B0=%u,BS=%u,B1=%u\n",
                 (unsigned int)status, word, busy_mask,
                 (unsigned int)busy_before,
                 (unsigned int)busy_after_start,
                 (unsigned int)busy_after_word);
        send_response(adc_buf);
#else
        send_response("ERR:301,ADC_BUSY_TRACE_UNSUPPORTED\n");
#endif
    }
    else if (strcmp(cmd_line, "ADC_SERIAL_TRACE0") == 0 ||
             strcmp(cmd_line, "ADC_SERIAL_TRACE1") == 0 ||
             strcmp(cmd_line, "ADC_SERIAL_NORD") == 0) {
#if defined(STM32F103xB) && (ACTIVE_MODE != MODE_TEST_USB) && \
    (ACTIVE_MODE != MODE_TEST_DAC)
        uint32_t data_trace = 0U;
        uint32_t busy_trace = 0U;
        uint8_t pulse_start = (strcmp(cmd_line, "ADC_SERIAL_NORD") != 0)
                                ? 1U : 0U;
        ads7861_pair_t pair = (strcmp(cmd_line, "ADC_SERIAL_TRACE1") == 0)
                                ? ADS7861_PAIR_1 : ADS7861_PAIR_0;
        ads7861_status_t status = ads7861_debug_serial_trace(
            &g_ads7861, pair, &data_trace, &busy_trace, pulse_start);
        char adc_buf[80];
        snprintf(adc_buf, sizeof(adc_buf),
                 "DATA:E=%u,D=%06lX,BM=%05lX\n",
                 (unsigned int)status,
                 (unsigned long)data_trace,
                 (unsigned long)busy_trace);
        send_response(adc_buf);
#else
        send_response("ERR:301,ADC_SERIAL_TRACE_UNSUPPORTED\n");
#endif
    }
    else if (strcmp(cmd_line, "ADC_FORCE_M1:0") == 0) {
#if defined(STM32F103xB)
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_11, GPIO_PIN_RESET);
        send_response("OK\n");
#else
        send_response("ERR:301,ADC_FORCE_M1_UNSUPPORTED\n");
#endif
    }
    else if (strcmp(cmd_line, "ADC_FORCE_M1:1") == 0) {
#if defined(STM32F103xB)
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_11, GPIO_PIN_SET);
        send_response("OK\n");
#else
        send_response("ERR:301,ADC_FORCE_M1_UNSUPPORTED\n");
#endif
    }
    else if (strcmp(cmd_line, "ADC_FORCE_M0:0") == 0) {
#if defined(STM32F103xB) && (ACTIVE_MODE != MODE_TEST_USB) && \
    (ACTIVE_MODE != MODE_TEST_DAC)
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, GPIO_PIN_RESET);
        send_response("OK\n");
#else
        send_response("ERR:301,ADC_FORCE_M0_UNSUPPORTED\n");
#endif
    }
    else if (strcmp(cmd_line, "ADC_FORCE_M0:1") == 0) {
#if defined(STM32F103xB) && (ACTIVE_MODE != MODE_TEST_USB) && \
    (ACTIVE_MODE != MODE_TEST_DAC)
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_0, GPIO_PIN_SET);
        send_response("OK\n");
#else
        send_response("ERR:301,ADC_FORCE_M0_UNSUPPORTED\n");
#endif
    }
    else if (strcmp(cmd_line, "ADC_SAMPLE_EDGE:RISING") == 0) {
        ads7861_set_bitbang_sample_after_falling(0U);
        send_response("OK\n");
    }
    else if (strcmp(cmd_line, "ADC_SAMPLE_EDGE:FALLING") == 0) {
        ads7861_set_bitbang_sample_after_falling(1U);
        send_response("OK\n");
    }
    else if (strcmp(cmd_line, "ADC_SAMPLE_EDGE:BEFORE") == 0) {
        ads7861_set_bitbang_sample_after_falling(2U);
        send_response("OK\n");
    }
    else if (strcmp(cmd_line, "ADC_SAMPLE_EDGE:SKIP1") == 0) {
        ads7861_set_bitbang_sample_after_falling(3U);
        send_response("OK\n");
    }
    else if (strcmp(cmd_line, "ADC_RD_RELEASE:0") == 0) {
        ads7861_set_bitbang_rd_release_bit(0U);
        send_response("OK\n");
    }
    else if (strcmp(cmd_line, "ADC_RD_RELEASE:1") == 0) {
        ads7861_set_bitbang_rd_release_bit(1U);
        send_response("OK\n");
    }
    else if (strcmp(cmd_line, "ADC_RD_RELEASE:2") == 0) {
        ads7861_set_bitbang_rd_release_bit(2U);
        send_response("OK\n");
    }
    else if (strcmp(cmd_line, "ADC_RD_RELEASE:15") == 0) {
        ads7861_set_bitbang_rd_release_bit(15U);
        send_response("OK\n");
    }
    else if (strcmp(cmd_line, "STOP") == 0) {
        /* Fail-safe: STOP must silence both continuous ADC USB and DAC. */
        adc_stream_stop();
        test_controller_stop();
        send_response("OK\n");
    } 
    else if (strcmp(cmd_line, "GET_RESULT") == 0) {
        char result_buf[256];
        test_controller_get_result(result_buf, sizeof(result_buf));
        send_response(result_buf);
    } 
    else if (strcmp(cmd_line, "GET_SAMPLES") == 0) {
        // Send samples using binary protocol wrapper
        test_controller_get_samples_bin();
    } 
    else if (strcmp(cmd_line, "GET_CALIB") == 0) {
        char calib_buf[512];
        snprintf(calib_buf, sizeof(calib_buf),
                 "DATA:dac_x2_a=%.6f,dac_x2_b=%.6f,adc1_r0_m=%.6f,adc1_r0_c=%.6f,adc1_r1_m=%.6f,adc1_r1_c=%.6f,adc1_r2_m=%.6f,adc1_r2_c=%.6f,adc2_r0_m=%.6f,adc2_r0_c=%.6f,adc2_r1_m=%.6f,adc2_r1_c=%.6f,adc2_r2_m=%.6f,adc2_r2_c=%.6f\n",
                 calib_coeffs.dac_a, calib_coeffs.dac_b,
                 calib_coeffs.adc1_m[0], calib_coeffs.adc1_c[0],
                 calib_coeffs.adc1_m[1], calib_coeffs.adc1_c[1],
                 calib_coeffs.adc1_m[2], calib_coeffs.adc1_c[2],
                 calib_coeffs.adc2_m[0], calib_coeffs.adc2_c[0],
                 calib_coeffs.adc2_m[1], calib_coeffs.adc2_c[1],
                 calib_coeffs.adc2_m[2], calib_coeffs.adc2_c[2]);
        send_response(calib_buf);
    } 
    else if (strncmp(cmd_line, "SET_CALIB:", 10) == 0) {
        char *params = cmd_line + 10;
        char *key_val = get_param_value(params, "KEY");
        char *val_val = get_param_value(params, "VALUE");
        
        if (key_val && val_val) {
            // Find key string (comma separated)
            char key[32];
            char *comma = strchr(key_val, ',');
            if (comma) {
                uint16_t key_len = comma - key_val;
                if (key_len >= sizeof(key)) key_len = sizeof(key) - 1;
                strncpy(key, key_val, key_len);
                key[key_len] = '\0';
            } else {
                strncpy(key, key_val, sizeof(key) - 1);
                key[sizeof(key) - 1] = '\0';
            }
            
            float val = atof(val_val);
            calibration_set(key, val);
            send_response("OK\n");
        } else {
            send_response("ERR:100,Invalid calibration parameter\n");
        }
    } 
    else if (strcmp(cmd_line, "SAVE_CALIB") == 0) {
        calibration_save();
        send_response("OK\n");
    } 
    else if (strcmp(cmd_line, "RESET_CALIB") == 0) {
        calibration_reset();
        send_response("OK\n");
    } 
    else {
        send_response("ERR:404,Unknown Command\n");
    }
}
