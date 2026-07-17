import json
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from signal_analyzer import SignalAnalyzerApp


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "report" / "images" / "result_app"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TESTS = [
    {"id": "01_freq_100hz", "frequency": 100, "center": 2.0,
     "amplitude": 1.0, "range": "3.3V"},
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
     "center": 0.15, "amplitude": 0.05, "range": "0.3V"},
    {"id": "09_amp_0p5_pm0p5_range3p3", "frequency": 1000,
     "center": 0.5, "amplitude": 0.5, "range": "3.3V"},
]


class HardwareScreenshotRunner:
    def __init__(self, app, window):
        self.app = app
        self.window = window
        self.single_test = len(sys.argv) > 1
        self.index = int(sys.argv[1]) if self.single_test else 0
        self.end_index = self.index + 1 if self.single_test else len(TESTS)
        self.results = []
        self.deadline = 0.0

    def start(self):
        port_index = self.window.combo_ports.findText("COM4")
        if port_index < 0:
            raise RuntimeError("COM4 is not available")
        self.window.combo_ports.setCurrentIndex(port_index)
        self.window.toggle_connection()
        if not self.window.serial_conn or not self.window.serial_conn.is_open:
            raise RuntimeError("Cannot connect the real app to COM4")
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
        periods_to_show = 12.0
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
            raise RuntimeError("COM4 was not restored after stream stop")
        else:
            QTimer.singleShot(100, self.wait_for_serial_restore)

    def finish_all(self):
        manifest = {
            "source": str(Path(__file__).resolve().parents[2] / "test.txt"),
            "hardware": "STM32F103 + COM4, real SignalAnalyzerApp capture",
            "assumptions": [
                "The repeated fourth 1000 Hz entry was interpreted as 10000 Hz.",
                "The requested range 0.4 was mapped to the available 0.3V range.",
            ],
            "tests": self.results,
        }
        manifest_name = (
            f"{self.results[0]['id']}_metadata.json"
            if self.single_test else "manifest.json"
        )
        (OUTPUT_DIR / manifest_name).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
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
