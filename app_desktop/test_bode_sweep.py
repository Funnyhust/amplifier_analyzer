import unittest
from types import SimpleNamespace

import numpy as np

from signal_analyzer import SweepWorker


class _FrameSerial:
    def __init__(self, data):
        self.data = bytearray(data)

    def read(self, size):
        chunk = self.data[:size]
        del self.data[:size]
        return bytes(chunk)


class BodeSweepTests(unittest.TestCase):
    def test_sample_rate_is_dense_and_capped_at_verified_stream_rate(self):
        self.assertEqual(SweepWorker.sample_rate_for_frequency(100), 5000)
        self.assertEqual(SweepWorker.sample_rate_for_frequency(1000), 50000)
        self.assertEqual(SweepWorker.sample_rate_for_frequency(10000), 140000)
        self.assertEqual(SweepWorker.sample_rate_for_frequency(20000), 140000)

    def test_compressed_stream_frame_decodes_both_adc_channels(self):
        ch1 = (np.arange(512, dtype=np.uint16) * 3) & 0x0FFF
        ch2 = (4095 - np.arange(512, dtype=np.uint16) * 5) & 0x0FFF
        packed = (ch1.astype(np.uint32) << 12) | ch2.astype(np.uint32)
        samples = np.column_stack((
            (packed >> 16) & 0xFF,
            (packed >> 8) & 0xFF,
            packed & 0xFF,
        )).astype(np.uint8).tobytes()
        payload = (
            (1234).to_bytes(4, "big") +
            (140077).to_bytes(4, "big") +
            (512).to_bytes(2, "big") + samples
        )
        crc = 0
        for value in payload:
            crc ^= value
        frame = (
            b"\xaa\xbb\x04" + len(payload).to_bytes(2, "big") +
            payload + bytes([crc])
        )
        worker = SweepWorker(
            SimpleNamespace(serial_conn=_FrameSerial(frame)),
            100, 20000, 5, 0.3,
        )
        sequence, fs, decoded_ch1, decoded_ch2 = worker._read_stream_frame()
        self.assertEqual(sequence, 1234)
        self.assertEqual(fs, 140077)
        np.testing.assert_array_equal(decoded_ch1, ch1)
        np.testing.assert_array_equal(decoded_ch2, ch2)


if __name__ == "__main__":
    unittest.main()
