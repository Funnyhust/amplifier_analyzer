"""
Module: dsp
Mục đích: Pure DSP functions — FFT, phase, gain, filter, unit formatting. KHÔNG import Qt.
Sections:
  - IMPORTS
  - SIGNAL DECODE
  - DSP COMPUTATIONS
  - UNIT FORMATTERS
Tác giả: Truong pc
"""

# ===== IMPORTS =====
import numpy as np

# ===== SIGNAL DECODE =====
def decode_osc_payload(payload: bytes, gain_factor: float):
    """
    Giải mã OSC payload thành 2 mảng voltage.
    Sẽ implement đầy đủ ở Story 2.3/4.1.
    Returns: (ch1_V: np.ndarray, ch2_V: np.ndarray)
    """
    raise NotImplementedError("Sẽ implement ở Story 2.3")

# ===== DSP COMPUTATIONS =====
def compute_fft(signal: np.ndarray, sample_rate: float):
    """Tính FFT. Returns: (freq_array, magnitude_dB)"""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

def compute_gain_rms(ch_in: np.ndarray, ch_out: np.ndarray) -> float:
    """Tính gain theo RMS. Returns: gain_dB (float)"""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

def compute_phase_fft(ch_in: np.ndarray, ch_out: np.ndarray,
                      freq_hz: float, sample_rate: float) -> float:
    """Tính phase difference. Returns: phase_deg in -180..+180"""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

def apply_lowpass_filter(signal: np.ndarray, cutoff_hz: float,
                         sample_rate: float, zi: np.ndarray):
    """Lowpass filter real-time với state. Returns: (filtered, zi_new)"""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

# ===== UNIT FORMATTERS =====
def format_voltage(v: float) -> str:
    """Auto-scale voltage: <0.1V → mV, >=0.1V → V"""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

def format_frequency(hz: float) -> str:
    """Auto-scale frequency: <1000 → Hz, >=1000 → kHz"""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

def format_phase(deg: float) -> str:
    """Format phase degrees."""
    raise NotImplementedError("Sẽ implement ở Story 4.1")

def format_gain(db: float) -> str:
    """Format gain dB."""
    raise NotImplementedError("Sẽ implement ở Story 4.1")
