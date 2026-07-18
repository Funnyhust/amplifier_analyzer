import json
import os
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from signal_analyzer import SignalAnalyzerApp


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "report" / "images" / "result_app"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CAPTURE_PORT = os.environ.get("AMPLIFIER_CAPTURE_PORT", "COM4")
CUSTOM_CAPTURE = "AMPLIFIER_CAPTURE_FREQUENCY" in os.environ

TESTS = [
    {"id": "01_freq_100hz", "frequency": 100, "center": 2.0,
     "amplitude": 1.0, "range": "3.3V", "periods_to_show": 6.0},
    {"id": "02_freq_1000hz", "frequency": 1000, "center": 2.0,
     "amplitude": 1.0, "range": "3.3V"},
    {"id": "03_freq_5000hz", "frequency": 5000, "center": 2.0,
     "amplitude": 1.0, "range": "3.3V"},
    {"id": "04_freq_10000hz", "frequency": 10000, "center": 2.0,
     "amplitude": 1.0, "range": "3.3V"},
    {"id": "05_freq_20000hz", "frequency": 20000, "center": 2.0,
     "amplitude": 1.0, "range": "3.3V"},
    {"id": "06_amp_1p65_pm1_range10", "frequency": 1000,
     "center": 1.65, "amplitude": 1.0, "range": "10V"},
    {"id": "07_amp_1p0_pm0p5_range10", "frequency": 1000,
     "center": 1.0, "amplitude": 0.5, "range": "10V"},
    {"id": "08_amp_0p15_pm0p05_range0p3", "frequency": 1000,
     "center": 0.15, "amplitude": 0.05, "range": "0.3V",
     "periods_to_show": 6.0},
    {"id": "09_amp_0p5_pm0p5_range3p3", "frequency": 1000,
     "center": 0.5, "amplitude": 0.5, "range": "3.3V"},
]

if CUSTOM_CAPTURE:
    TESTS = [{
        "id": os.environ.get("AMPLIFIER_CAPTURE_ID", "custom_capture"),
        "frequency": float(os.environ["AMPLIFIER_CAPTURE_FREQUENCY"]),
        "center": float(os.environ.get("AMPLIFIER_CAPTURE_CENTER", "2.0")),
        "amplitude": float(os.environ.get("AMPLIFIER_CAPTURE_AMPLITUDE", "1.0")),
        "range": os.environ.get("AMPLIFIER_CAPTURE_RANGE", "10V"),
        "dut_name": os.environ.get("AMPLIFIER_CAPTURE_DUT_NAME", "DUT 1"),
        "target_gain_linear": float(
            os.environ.get("AMPLIFIER_CAPTURE_TARGET_GAIN", "1.0")
        ),
        "target_phase_deg": float(
            os.environ.get("AMPLIFIER_CAPTURE_TARGET_PHASE", "0.0")
        ),
    }]


class HardwareScreenshotRunner:
    def __init__(self, app, window):
        self.app = app
        self.window = window
        self.single_test = CUSTOM_CAPTURE or len(sys.argv) > 1
        self.index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
        self.end_index = self.index + 1 if self.single_test else len(TESTS)
        self.results = []
        self.deadline = 0.0

    def start(self):
        port_index = self.window.combo_ports.findText(CAPTURE_PORT)
        if port_index < 0:
            raise RuntimeError(f"{CAPTURE_PORT} is not available")
        self.window.combo_ports.setCurrentIndex(port_index)
        self.window.toggle_connection()
        if not self.window.serial_conn or not self.window.serial_conn.is_open:
            raise RuntimeError(
                f"Cannot connect the real app to {CAPTURE_PORT}"
            )
        self.window.chk_follow_stream.setChecked(True)
        self.window.chk_reconstruct_ch2_dc.setChecked(True)
        self.run_next()

    def run_next(self):
        if self.index >= self.end_index:
            self.finish_all()
            return
        test = TESTS[self.index]
        self.window.setWindowTitle(
            f"Signal Analyzer Pro — REAL HARDWARE — {test['id']}"
        )
        self.window.view_tabs.setCurrentIndex(0)
        self.window.ana_combo_wave.setCurrentText("SINE")
        self.window.ana_spin_freq.setValue(float(test["frequency"]))
        self.window.ana_spin_amp.setValue(float(test["amplitude"]))
        self.window.ana_spin_offset.setValue(float(test["center"] - 1.65))
        self.window.ana_spin_fs.setValue(140000.0)
        range_index = self.window.ana_combo_range.findData(test["range"])
        self.window.ana_combo_range.setCurrentIndex(range_index)
        if "dut_name" in test:
            self.window.edit_dut_name.setText(test["dut_name"])
        if "target_gain_linear" in test:
            self.window.spin_target_gain_linear.setValue(
                test["target_gain_linear"]
            )
        if "target_phase_deg" in test:
            self.window.spin_target_phase.setValue(test["target_phase_deg"])
        self.window.save_dut_settings()
        periods_to_show = float(test.get("periods_to_show", 12.0))
        view_seconds = max(0.001, periods_to_show / test["frequency"])
        self.window.spin_view_window.setValue(view_seconds)

        if not self.window.apply_range_config(False):
            raise RuntimeError(f"Range configuration failed for {test['id']}")
        if not self.window.apply_device_config(False):
            raise RuntimeError(
                f"Device configuration failed for {test['id']}: "
                f"{self.window.last_command_response}"
            )
        self.window.toggle_live("ANALYZER")
        QTimer.singleShot(3000, self.capture_waveform)

    def capture_waveform(self):
        test = TESTS[self.index]
        if not self.window.last_communication_ok:
            raise RuntimeError(
                f"Stream failed for {test['id']}: "
                f"{self.window.last_communication_error}"
            )
        self.window.view_tabs.setCurrentIndex(0)
        visible_channels = [
            values for values in (
                self.window.last_raw_ch1, self.window.last_raw_ch2
            ) if values is not None and len(values)
        ]
        if visible_channels:
            lower = min(float(values.min()) for values in visible_channels)
            upper = max(float(values.max()) for values in visible_channels)
            span = max(upper - lower, 0.01)
            padding = max(0.08 * span, 0.005)
            self.window.plot_osc.setYRange(
                lower - padding, upper + padding, padding=0.0
            )
        self.app.processEvents()
        waveform_path = OUTPUT_DIR / f"{test['id']}_waveform.png"
        if not self.window.grab().save(str(waveform_path), "PNG"):
            raise RuntimeError(f"Cannot save {waveform_path}")
        QTimer.singleShot(350, self.capture_results)

    def capture_results(self):
        test = TESTS[self.index]
        waveform_path = OUTPUT_DIR / f"{test['id']}_waveform.png"
        self.window.view_tabs.setCurrentIndex(2)
        self.app.processEvents()
        result_path = OUTPUT_DIR / f"{test['id']}_results.png"
        if not self.window.grab().save(str(result_path), "PNG"):
            raise RuntimeError(f"Cannot save {result_path}")

        self.results.append({
            **test,
            "requested_fs": 140000,
            "displayed_fs": self.window.ana_spin_fs.value(),
            "waveform_image": waveform_path.name,
            "results_image": result_path.name,
            "communication_ok": self.window.last_communication_ok,
            "communication_error": self.window.last_communication_error,
            "ch2_dc_status": self.window.lbl_ch2_dc_status.text(),
            "dut_setup": {
                "name": self.window.edit_dut_name.text().strip() or "DUT 1",
                "target_gain_linear": (
                    self.window.spin_target_gain_linear.value()
                ),
                "target_gain_db": self.window.target_gain_db(),
                "target_phase_deg": self.window.spin_target_phase.value(),
                "gain_tolerance_db": self.window.spin_tol_gain.value(),
                "phase_tolerance_deg": self.window.spin_tol_phase.value(),
            },
            "ch1_metrics": (
                self.window.last_ch1_metrics.to_dict()
                if self.window.last_ch1_metrics else None
            ),
            "ch2_metrics": (
                self.window.last_ch2_metrics.to_dict()
                if self.window.last_ch2_metrics else None
            ),
            "dut_metrics": (
                self.window.last_dut_metrics.to_dict()
                if self.window.last_dut_metrics else None
            ),
            "evaluation": (
                self.window.last_evaluation.to_dict()
                if self.window.last_evaluation else None
            ),
        })
        print(
            f"CAPTURED {self.index + 1}/{len(TESTS)} {test['id']}",
            flush=True,
        )
        self.window.view_tabs.setCurrentIndex(0)
        self.window.toggle_live("ANALYZER")
        self.deadline = time.monotonic() + 6.0
        QTimer.singleShot(100, self.wait_for_serial_restore)

    def wait_for_serial_restore(self):
        restored = (
            self.window.capture_worker is None
            and self.window.serial_conn is not None
            and self.window.serial_conn.is_open
        )
        if restored:
            self.index += 1
            QTimer.singleShot(250, self.run_next)
        elif time.monotonic() >= self.deadline:
            raise RuntimeError(
                f"{CAPTURE_PORT} was not restored after stream stop"
            )
        else:
            QTimer.singleShot(100, self.wait_for_serial_restore)

    def finish_all(self):
        source = (
            "Custom capture parameters from environment"
            if CUSTOM_CAPTURE
            else str(Path(__file__).resolve().parents[2] / "test.txt")
        )
        assumptions = [] if CUSTOM_CAPTURE else [
            "The repeated fourth 1000 Hz entry was interpreted as 10000 Hz.",
            "The requested range 0.4 was mapped to the available 0.3V range.",
        ]
        manifest = {
            "source": source,
            "hardware": (
                f"STM32F103 + {CAPTURE_PORT}, real SignalAnalyzerApp capture"
            ),
            "assumptions": assumptions,
            "tests": self.results,
        }
        if self.single_test:
            metadata_path = OUTPUT_DIR / f"{self.results[0]['id']}_metadata.json"
            metadata_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        else:
            (OUTPUT_DIR / "manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            for result in self.results:
                per_test_manifest = {**manifest, "tests": [result]}
                metadata_path = OUTPUT_DIR / f"{result['id']}_metadata.json"
                metadata_path.write_text(
                    json.dumps(per_test_manifest, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        if self.window.serial_conn and self.window.serial_conn.is_open:
            self.window.stop_device_safely()
            self.window.serial_conn.close()
        print(f"DONE {len(self.results)} tests -> {OUTPUT_DIR}", flush=True)
        self.app.quit()


app = QApplication(sys.argv)
app.setStyle("Fusion")
window = SignalAnalyzerApp()
window.resize(1600, 950)
window.show()
runner = HardwareScreenshotRunner(app, window)
QTimer.singleShot(500, runner.start)
raise SystemExit(app.exec())
