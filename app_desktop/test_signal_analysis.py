import math
import unittest

import numpy as np

from signal_analysis import (
    DAC_OUTPUT_BIAS_VOLTS,
    DUT_RANGE_DEFAULT_SCALES,
    analyze_channel,
    analyze_dut,
    calculate_sampling_quality,
    convert_measurement_channels,
    downsample_extrema_indices,
    downsample_uniform_indices,
    evaluate_pass_fail,
    reconstruct_zero_intercept_vout,
    raw_adc_to_volts,
)


class SamplingQualityTests(unittest.TestCase):
    def assert_close(self, actual, expected, places=3):
        self.assertAlmostEqual(actual, expected, places=places)

    def test_required_sampling_cases(self):
        cases = [
            (20_000, 200_000, 10.0, 4.894, 1.637, 0.50, "WARNING_POC_ONLY"),
            (20_000, 500_000, 25.0, 0.789, 0.263, -2.50, "WARNING_DAC_NOT_SETTLED"),
            (20_000, 1_000_000, 50.0, 0.197, 0.066, -3.50, "WARNING_DAC_NOT_SETTLED"),
            (2_000, 200_000, 100.0, 0.049, 0.016, 0.50, "WARNING_DAC_SETTLING_BORDERLINE"),
        ]
        for freq, fs, n, peak, zoh, margin, warning in cases:
            with self.subTest(freq=freq, fs=fs):
                result = calculate_sampling_quality(freq, fs)
                self.assert_close(result.samples_per_cycle, n)
                self.assert_close(result.peak_sampling_error_pct, peak)
                self.assert_close(result.zoh_droop_pct, zoh)
                self.assert_close(result.settling_margin_us, margin)
                self.assertIn(warning, result.warnings)

    def test_channel_and_dut_use_ac_rms(self):
        fs, freq = 200_000.0, 2_000.0
        t = np.arange(2000) / fs
        ch1 = 0.3 * np.sin(2 * np.pi * freq * t) + 0.1
        ch2 = 0.6 * np.sin(2 * np.pi * freq * t - math.radians(30)) - 0.2
        m1 = analyze_channel(ch1, fs, freq)
        m2 = analyze_channel(ch2, fs, freq)
        dut = analyze_dut(m1, m2, 20 * math.log10(2), 0.1, freq)
        self.assertAlmostEqual(m1.vmean, 0.1, places=3)
        self.assertAlmostEqual(m1.vrms_ac, 0.3 / math.sqrt(2), places=3)
        self.assertAlmostEqual(dut.gain_linear, 2.0, places=3)
        self.assertAlmostEqual(dut.phase_shift_deg, -30.0, places=2)

    def test_measurement_warning_prevents_absolute_pass(self):
        fs, freq = 200_000.0, 20_000.0
        t = np.arange(1024) / fs
        m1 = analyze_channel(0.3 * np.sin(2 * np.pi * freq * t), fs, freq)
        m2 = analyze_channel(0.24 * np.sin(2 * np.pi * freq * t), fs, freq)
        dut = analyze_dut(m1, m2, -1.9382, 0.2, freq)
        evaluation = evaluate_pass_fail(
            calculate_sampling_quality(freq, fs), m1, m2, dut, freq
        )
        self.assertEqual(evaluation.status, "WARNING")
        self.assertIn("WARNING_POC_ONLY", evaluation.reasons)

    def test_ads7861_offset_binary_transport_scale(self):
        volts = raw_adc_to_volts(np.array([0, 2048, 4095]))
        self.assertAlmostEqual(volts[0], -2.5, places=6)
        self.assertAlmostEqual(volts[1], 0.0, places=6)
        self.assertAlmostEqual(volts[2], 2.5 * 2047 / 2048, places=6)

    def test_display_downsampling_keeps_real_sample_timestamps(self):
        ch1 = np.array([5, 1, 4, 3, 2, 0, 0, 2, 3, 5, 4, 1])
        ch2 = np.array([0, 2, 4, 5, 3, 1, 5, 4, 0, 1, 2, 3])
        indices = downsample_extrema_indices((ch1, ch2), 8)
        # Two six-sample buckets retain each channel's extrema at their real
        # positions, sorted in time. No value is moved to a bucket boundary.
        np.testing.assert_array_equal(indices, [0, 3, 5, 6, 8, 9])

    def test_uniform_display_downsampling_preserves_waveform_spacing(self):
        indices = downsample_uniform_indices(12, 5)
        np.testing.assert_array_equal(indices, [0, 2, 5, 8, 11])

    def test_dut_range_scale_never_changes_direct_vin(self):
        raw = np.array([1024, 2048, 3072])
        vin, vout = convert_measurement_channels(
            raw, raw,
            vin_calibration_scale=1.0,
            vin_calibration_offset_mv=0.0,
            vout_range_scale=100.0,
            vout_range_offset_mv=0.0,
        )
        expected_vin = raw_adc_to_volts(raw) + 2.5
        np.testing.assert_allclose(vin, expected_vin)
        np.testing.assert_allclose(vout, raw_adc_to_volts(raw) * 100.0)

    def test_dut_range_nominal_scale_mapping(self):
        np.testing.assert_allclose(
            DUT_RANGE_DEFAULT_SCALES,
            (-10.0 / 47.0, -10.0 / 4.7, -10.0 / 1.5),
        )
        raw = np.array([1024, 2048, 3072])
        base = raw_adc_to_volts(raw)
        for scale in DUT_RANGE_DEFAULT_SCALES:
            with self.subTest(scale=scale):
                _, vout = convert_measurement_channels(
                    raw, raw, vout_range_scale=scale
                )
                np.testing.assert_allclose(vout, base * scale)

    def test_explicit_zero_intercept_dc_reconstruction(self):
        phase = np.linspace(0.0, 4.0 * np.pi, 1000, endpoint=False)
        vin = 2.0 + np.sin(phase)
        vout_ac = 3.0 * np.sin(phase)
        reconstructed, gain, inferred_dc = reconstruct_zero_intercept_vout(
            vin, vout_ac, vin_dc=2.0
        )
        self.assertAlmostEqual(gain, 3.0, places=6)
        self.assertAlmostEqual(inferred_dc, 6.0, places=6)
        np.testing.assert_allclose(reconstructed, 6.0 + vout_ac, atol=1e-12)

    def test_dac_bias_matches_firmware_output_center(self):
        self.assertAlmostEqual(DAC_OUTPUT_BIAS_VOLTS, 1.65, places=9)


if __name__ == "__main__":
    unittest.main()
