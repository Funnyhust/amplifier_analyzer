"""Signal-quality calculations shared by the UI, simulation and tests."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Optional

import numpy as np


MCP4822_SETTLING_TIME_US = 4.5
ADC_MAX_CODE = 4095
ADS7861_MIDSCALE_CODE = 2048.0
ADS7861_VREF_VOLTS = 2.5
DAC_OUTPUT_BIAS_VOLTS = 1.65
# U4A is an inverting AC-coupled CH2 frontend with R26=10k. Relay feedback
# resistors are 47k, 4.7k and 1.5k, so reconstruct Vin with -Rin/Rfeedback.
DUT_RANGE_DEFAULT_SCALES = (-10.0 / 47.0, -10.0 / 4.7, -10.0 / 1.5)


@dataclass
class SamplingQuality:
    signal_frequency_hz: float
    sample_rate_sps: float
    period_us: float
    sample_interval_us: float
    samples_per_cycle: float
    peak_sampling_error_pct: float
    zoh_droop_pct: float
    dac_settling_time_us: float
    settling_margin_us: float
    status: str
    summary: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ChannelMetrics:
    vmax: float = 0.0
    vmin: float = 0.0
    vpp: float = 0.0
    vpeak: float = 0.0
    vrms_total: float = 0.0
    vrms_ac: float = 0.0
    vmean: float = 0.0
    sine_peak_est: float = 0.0
    frequency_hz: float = 0.0
    period_us: Optional[float] = None
    noise_rms: Optional[float] = None
    sine_phase_deg: Optional[float] = None
    clipping: bool = False
    saturation: bool = False
    sample_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DUTMetrics:
    gain_linear: Optional[float]
    gain_db: Optional[float]
    target_gain_db: float
    gain_error_db: Optional[float]
    gain_tolerance_db: float
    phase_shift_deg: Optional[float]
    delay_us: Optional[float]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvaluationResult:
    status: str
    reasons: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_sampling_quality(
    signal_frequency_hz: float,
    sample_rate_sps: float,
    settling_time_us: float = MCP4822_SETTLING_TIME_US,
) -> SamplingQuality:
    """Evaluate sampling and MCP4822 settling limits for one configuration."""
    if signal_frequency_hz <= 0 or sample_rate_sps <= 0:
        raise ValueError("signal frequency and sample rate must be positive")

    samples_per_cycle = sample_rate_sps / signal_frequency_hz
    period_us = 1e6 / signal_frequency_hz
    sample_interval_us = 1e6 / sample_rate_sps
    x = math.pi / samples_per_cycle
    peak_error_pct = (1.0 - math.cos(x)) * 100.0
    zoh_droop_pct = (1.0 - math.sin(x) / x) * 100.0
    margin_us = sample_interval_us - settling_time_us

    warnings: list[str] = []
    if samples_per_cycle < 10.0:
        warnings.append("WARNING_SAMPLE_TOO_LOW")
    elif samples_per_cycle < 25.0:
        warnings.append("WARNING_POC_ONLY")
    if peak_error_pct > 1.0:
        warnings.append("WARNING_PEAK_ERROR_GT_1_PERCENT")
    if margin_us < 0.0:
        warnings.append("WARNING_DAC_NOT_SETTLED")
    elif margin_us < 1.0:
        warnings.append("WARNING_DAC_SETTLING_BORDERLINE")

    if "WARNING_DAC_NOT_SETTLED" in warnings:
        summary = "WARNING / DAC not settled"
    elif "WARNING_SAMPLE_TOO_LOW" in warnings:
        summary = "WARNING / sampling too low"
    elif "WARNING_POC_ONLY" in warnings:
        summary = "WARNING / POC only"
    elif "WARNING_DAC_SETTLING_BORDERLINE" in warnings:
        summary = "WARNING / settling borderline"
    elif warnings:
        summary = "WARNING / limited confidence"
    else:
        summary = "OK"

    return SamplingQuality(
        signal_frequency_hz=float(signal_frequency_hz),
        sample_rate_sps=float(sample_rate_sps),
        period_us=period_us,
        sample_interval_us=sample_interval_us,
        samples_per_cycle=samples_per_cycle,
        peak_sampling_error_pct=peak_error_pct,
        zoh_droop_pct=zoh_droop_pct,
        dac_settling_time_us=settling_time_us,
        settling_margin_us=margin_us,
        status="WARNING" if warnings else "OK",
        summary=summary,
        warnings=warnings,
    )


def raw_adc_to_volts(
    raw_codes: np.ndarray,
    scale: float = 1.0,
    offset_mv: float = 0.0,
) -> np.ndarray:
    raw = np.asarray(raw_codes, dtype=np.float64)
    # Firmware transports ADS7861 signed samples as 12-bit offset-binary.
    base_volts = ((raw - ADS7861_MIDSCALE_CODE) /
                  ADS7861_MIDSCALE_CODE) * ADS7861_VREF_VOLTS
    return base_volts * float(scale) + float(offset_mv) / 1000.0


def convert_measurement_channels(
    vin_raw: np.ndarray,
    vout_raw: np.ndarray,
    vin_calibration_scale: float = 1.0,
    vin_calibration_offset_mv: float = 0.0,
    vout_range_scale: float = 1.0,
    vout_range_offset_mv: float = 0.0,
):
    """Convert the direct Vin path and ranged DUT Vout path independently."""
    # Vin is wired directly to the ADC and is biased by ADS7861 VREF. Its only
    # allowed correction is the direct-channel calibration; the selected DUT
    # relay range must never affect this expression.
    vin = raw_adc_to_volts(
        vin_raw, vin_calibration_scale, vin_calibration_offset_mv
    ) + ADS7861_VREF_VOLTS
    vout = raw_adc_to_volts(
        vout_raw, vout_range_scale, vout_range_offset_mv
    )
    return vin, vout


def reconstruct_zero_intercept_vout(vin, vout_ac, vin_dc=None):
    """Infer Vout DC under the explicit model Vout = gain * Vin."""
    vin = np.asarray(vin, dtype=np.float64)
    vout_ac = np.asarray(vout_ac, dtype=np.float64)
    if vin.size != vout_ac.size or vin.size < 4:
        raise ValueError("Vin and Vout must contain at least four samples")
    vin_centered = vin - np.mean(vin)
    vout_centered = vout_ac - np.mean(vout_ac)
    vin_energy = float(np.dot(vin_centered, vin_centered))
    vout_energy = float(np.dot(vout_centered, vout_centered))
    if vin_energy <= 1e-12 or vout_energy <= 1e-12:
        raise ValueError("Vin has no measurable AC component")
    gain_magnitude = math.sqrt(vout_energy / vin_energy)
    correlation = float(np.dot(vin_centered, vout_centered))
    signed_gain = gain_magnitude if correlation >= 0.0 else -gain_magnitude
    input_dc = float(np.mean(vin) if vin_dc is None else vin_dc)
    inferred_dc = signed_gain * input_dc
    return vout_centered + inferred_dc, signed_gain, inferred_dc


def downsample_extrema_indices(channels, max_points: int) -> np.ndarray:
    """Select real, time-ordered extrema shared by multiple channels.

    The returned indices always reference original samples. This avoids the
    false ramps produced by pairing a bucket minimum with its start time and a
    bucket maximum with its end time when those extrema occurred in the
    opposite order.
    """
    arrays = [np.asarray(channel) for channel in channels]
    if not arrays:
        return np.array([], dtype=np.int64)
    count = arrays[0].size
    if any(channel.size != count for channel in arrays):
        raise ValueError("all channels must contain the same number of samples")
    if count <= max_points:
        return np.arange(count, dtype=np.int64)

    extrema_per_group = 2 * len(arrays)
    group_limit = max(1, int(max_points) // extrema_per_group)
    bucket = int(np.ceil(count / float(group_limit)))
    full_groups = count // bucket
    used = full_groups * bucket
    bases = np.arange(full_groups, dtype=np.int64) * bucket
    selected = []

    for channel in arrays:
        if full_groups:
            grouped = channel[:used].reshape(full_groups, bucket)
            selected.append(bases + grouped.argmin(axis=1))
            selected.append(bases + grouped.argmax(axis=1))
        if used < count:
            tail = channel[used:]
            selected.append(np.array([used + int(tail.argmin())]))
            selected.append(np.array([used + int(tail.argmax())]))

    return np.unique(np.concatenate(selected)).astype(np.int64, copy=False)


def downsample_uniform_indices(count: int, max_points: int) -> np.ndarray:
    """Return evenly spaced original-sample indices for waveform rendering."""
    count = int(count)
    max_points = int(max_points)
    if count <= 0 or max_points <= 0:
        return np.array([], dtype=np.int64)
    if count <= max_points:
        return np.arange(count, dtype=np.int64)
    return np.linspace(0, count - 1, max_points, dtype=np.int64)


def _positive_zero_crossing_frequency(samples: np.ndarray, fs: float) -> float:
    centered = samples - np.mean(samples)
    indices = np.flatnonzero((centered[:-1] <= 0.0) & (centered[1:] > 0.0))
    if indices.size < 2:
        return 0.0
    crossings = []
    for index in indices:
        y0, y1 = centered[index], centered[index + 1]
        fraction = -y0 / (y1 - y0) if y1 != y0 else 0.0
        crossings.append((index + fraction) / fs)
    periods = np.diff(crossings)
    periods = periods[periods > 0.0]
    return float(1.0 / np.median(periods)) if periods.size else 0.0


def _sine_fit(samples: np.ndarray, fs: float, frequency_hz: float):
    if frequency_hz <= 0.0 or samples.size < 4:
        return None
    t = np.arange(samples.size, dtype=np.float64) / fs
    omega_t = 2.0 * np.pi * frequency_hz * t
    matrix = np.column_stack((np.sin(omega_t), np.cos(omega_t), np.ones_like(t)))
    coeffs, _, _, _ = np.linalg.lstsq(matrix, samples, rcond=None)
    sin_coeff, cos_coeff, offset = coeffs
    fitted = matrix @ coeffs
    amplitude = float(np.hypot(sin_coeff, cos_coeff))
    phase_deg = float(np.degrees(np.arctan2(cos_coeff, sin_coeff)))
    residual_rms = float(np.sqrt(np.mean((samples - fitted) ** 2)))
    return amplitude, float(offset), phase_deg, residual_rms


def analyze_channel(
    samples,
    fs: float,
    target_frequency_hz: Optional[float] = None,
    raw_codes=None,
) -> ChannelMetrics:
    values = np.asarray(samples, dtype=np.float64)
    if values.size == 0 or fs <= 0:
        return ChannelMetrics()

    vmean = float(np.mean(values))
    ac = values - vmean
    vmax = float(np.max(values))
    vmin = float(np.min(values))
    vpp = vmax - vmin
    vrms_ac = float(np.sqrt(np.mean(ac * ac)))
    frequency_hz = _positive_zero_crossing_frequency(values, fs)
    fit_frequency = float(target_frequency_hz or frequency_hz)
    fit = _sine_fit(values, fs, fit_frequency)

    saturation = False
    raw_span = None
    if raw_codes is not None:
        raw = np.asarray(raw_codes)
        saturation = bool(np.any(raw <= 1) or np.any(raw >= ADC_MAX_CODE - 1))
        raw_span = float(np.max(raw) - np.min(raw)) if raw.size else 0.0

    clipping = saturation
    # Ignore quantized noise/near-flat channels, and require a longer plateau
    # than the repeated codes naturally produced near a sampled sine peak.
    plateau_eligible = raw_span is None or raw_span >= ADC_MAX_CODE * 0.01
    if (not clipping and plateau_eligible and vpp > 0.0 and
            values.size >= 10):
        edge_band = max(vpp * 0.002, 1e-9)
        near_top = np.abs(values - vmax) <= edge_band
        near_bottom = np.abs(values - vmin) <= edge_band
        # Four repeated extrema can occur from ADC/DAC quantization.
        top_run = (near_top[:-4] & near_top[1:-3] & near_top[2:-2] &
                   near_top[3:-1] & near_top[4:])
        bottom_run = (near_bottom[:-4] & near_bottom[1:-3] &
                      near_bottom[2:-2] & near_bottom[3:-1] & near_bottom[4:])
        clipping = bool(np.any(top_run) or np.any(bottom_run))

    phase = fit[2] if fit else None
    noise = fit[3] if fit else None
    sine_peak = fit[0] if fit else vrms_ac * math.sqrt(2.0)
    period_us = 1e6 / frequency_hz if frequency_hz > 0.0 else None
    return ChannelMetrics(
        vmax=vmax,
        vmin=vmin,
        vpp=vpp,
        vpeak=vpp / 2.0,
        vrms_total=float(np.sqrt(np.mean(values * values))),
        vrms_ac=vrms_ac,
        vmean=vmean,
        sine_peak_est=sine_peak,
        frequency_hz=frequency_hz,
        period_us=period_us,
        noise_rms=noise,
        sine_phase_deg=phase,
        clipping=clipping,
        saturation=saturation,
        sample_count=int(values.size),
    )


def analyze_dut(
    ch1: ChannelMetrics,
    ch2: ChannelMetrics,
    target_gain_db: float,
    gain_tolerance_db: float,
    target_frequency_hz: Optional[float] = None,
) -> DUTMetrics:
    if ch1.vrms_ac <= 1e-12:
        return DUTMetrics(None, None, target_gain_db, None, gain_tolerance_db, None, None)
    gain_linear = ch2.vrms_ac / ch1.vrms_ac
    gain_db = 20.0 * math.log10(gain_linear) if gain_linear > 0.0 else None
    gain_error = gain_db - target_gain_db if gain_db is not None else None
    phase = None
    if ch1.sine_phase_deg is not None and ch2.sine_phase_deg is not None:
        phase = (ch2.sine_phase_deg - ch1.sine_phase_deg + 180.0) % 360.0 - 180.0
    frequency = target_frequency_hz or ch1.frequency_hz
    delay_us = phase / (360.0 * frequency) * 1e6 if phase is not None and frequency > 0 else None
    return DUTMetrics(
        gain_linear=gain_linear,
        gain_db=gain_db,
        target_gain_db=target_gain_db,
        gain_error_db=gain_error,
        gain_tolerance_db=gain_tolerance_db,
        phase_shift_deg=phase,
        delay_us=delay_us,
    )


def evaluate_pass_fail(
    sampling: SamplingQuality,
    ch1: ChannelMetrics,
    ch2: ChannelMetrics,
    dut: DUTMetrics,
    target_frequency_hz: float,
    frequency_tolerance_pct: Optional[float] = None,
    target_amplitude_vpeak: Optional[float] = None,
    amplitude_tolerance_pct: Optional[float] = None,
    communication_ok: bool = True,
    data_complete: bool = True,
) -> EvaluationResult:
    failures: list[str] = []
    warnings = list(sampling.warnings)
    if not communication_ok:
        failures.append("COMMUNICATION_ERROR")
    if not data_complete:
        failures.append("WARNING_DATA_LOSS")
    if ch1.clipping or ch2.clipping:
        failures.append("SIGNAL_CLIPPING")
    if ch1.saturation or ch2.saturation:
        failures.append("ADC_SATURATION")
    if dut.gain_error_db is None:
        failures.append("GAIN_NOT_AVAILABLE")
    elif abs(dut.gain_error_db) > dut.gain_tolerance_db:
        failures.append("GAIN_OUT_OF_TOLERANCE")

    if frequency_tolerance_pct is not None and target_frequency_hz > 0.0:
        measured = ch1.frequency_hz
        error_pct = abs(measured - target_frequency_hz) / target_frequency_hz * 100.0
        if measured <= 0.0 or error_pct > frequency_tolerance_pct:
            failures.append("FREQUENCY_OUT_OF_TOLERANCE")
    if amplitude_tolerance_pct is not None and target_amplitude_vpeak is not None:
        amplitude_error = abs(ch1.sine_peak_est - target_amplitude_vpeak)
        amplitude_error_pct = amplitude_error / max(abs(target_amplitude_vpeak), 1e-12) * 100.0
        if amplitude_error_pct > amplitude_tolerance_pct:
            failures.append("AMPLITUDE_OUT_OF_TOLERANCE")

    if failures:
        return EvaluationResult("FAIL", failures + warnings)
    if warnings:
        return EvaluationResult("WARNING", warnings)
    return EvaluationResult("PASS", ["ALL_CHECKS_PASSED"])
