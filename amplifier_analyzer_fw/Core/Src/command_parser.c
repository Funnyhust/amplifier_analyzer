#include "command_parser.h"
#include "test_controller.h"
#include "calibration.h"
#include "range_control.h"
#include "config.h"
#include "protocol.h"
#include "usbd_cdc_if.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

#define CMD_BUF_SIZE 256
static char cmd_buf[CMD_BUF_SIZE];
static uint16_t cmd_idx = 0;
static volatile uint8_t pending_ready = 0U;

extern USBD_HandleTypeDef hUsbDeviceFS;

static void send_response(const char *resp) {
    uint16_t len = strlen(resp);
    protocol_send_raw((uint8_t *)resp, len);
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

    /* Keep pending_ready set while executing so the USB ISR cannot overwrite it. */
    command_parser_execute(cmd_buf);
    cmd_idx = 0U;
    pending_ready = 0U;
}

static char* get_param_value(char *str, const char *key) {
    char *p = strstr(str, key);
    if (!p) return NULL;
    p += strlen(key);
    if (*p == '=') {
        return p + 1;
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
        
        test_controller_configure(&cfg);
        send_response("OK\n");
    } 
    else if (strcmp(cmd_line, "START") == 0) {
        test_controller_start();
        send_response("OK\n");
    } 
    else if (strcmp(cmd_line, "STOP") == 0) {
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
