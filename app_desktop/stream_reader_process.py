"""Dedicated USB CDC reader used by the desktop live-stream worker.

This process owns COM while streaming so Qt rendering and DSP in the GUI
process can never back-pressure the STM32 merely by holding Python's GIL.
Messages are length-prefixed pickles sent over a localhost TCP socket.
"""

import functools
import pickle
import socket
import struct
import sys

import numpy as np
import serial


UI_BLOCK_SAMPLES = 4096
output_socket = None


def send_message(message):
    payload = pickle.dumps(message, protocol=pickle.HIGHEST_PROTOCOL)
    output_socket.sendall(struct.pack("<I", len(payload)) + payload)


def read_exact(connection, size):
    data = bytearray()
    while len(data) < size:
        chunk = connection.read(size - len(data))
        if not chunk:
            raise TimeoutError(f"short stream read: {len(data)}/{size}")
        data.extend(chunk)
    return bytes(data)


def read_line_command(connection, command):
    connection.reset_input_buffer()
    connection.write(command)
    connection.flush()
    return connection.readline().decode("utf-8", errors="replace").strip()


def main():
    global output_socket
    port = sys.argv[1]
    sample_rate = int(sys.argv[2])
    message_port = int(sys.argv[3])
    output_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    output_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF,
                             4 * 1024 * 1024)
    output_socket.connect(("127.0.0.1", message_port))
    connection = serial.Serial(port, 115200, timeout=5.0, write_timeout=1.0)
    try:
        try:
            connection.set_buffer_size(rx_size=4 * 1024 * 1024,
                                       tx_size=64 * 1024)
        except (AttributeError, NotImplementedError, OSError):
            pass
        if read_line_command(connection, b"START\n") != "OK":
            raise RuntimeError("Device did not acknowledge START.")
        command = f"ADC_USB_STREAM_START:FS={sample_rate}\n".encode()
        connection.write(command)
        connection.flush()
        if connection.readline().decode("utf-8", errors="replace").strip() != "OK":
            raise RuntimeError("Device did not start ADC USB stream.")

        expected_sequence = None
        pending_ch1 = []
        pending_ch2 = []
        pending_count = 0
        first_pending_sequence = None
        resyncing = False

        while True:
            first = read_exact(connection, 1)
            if first != b"\xaa":
                if not resyncing:
                    send_message({
                        "kind": "warning",
                        "message": f"stream byte resync after prefix 0x{first.hex()}",
                    })
                resyncing = True
                pending_ch1 = []
                pending_ch2 = []
                pending_count = 0
                first_pending_sequence = None
                continue
            header = first + read_exact(connection, 4)
            expected_length = (
                10 + 512 * 3 if header[2] == 0x04 else
                10 + 512 * 4 if header[2] == 0x01 else 0
            )
            payload_length = int.from_bytes(header[3:5], "big")
            if (header[:2] != b"\xaa\xbb" or expected_length == 0 or
                    payload_length != expected_length):
                if not resyncing:
                    send_message({
                        "kind": "warning",
                        "message": f"stream header resync: {header.hex(' ')}",
                    })
                resyncing = True
                pending_ch1 = []
                pending_ch2 = []
                pending_count = 0
                first_pending_sequence = None
                continue
            payload = read_exact(connection, payload_length)
            received_crc = read_exact(connection, 1)[0]
            calculated_crc = functools.reduce(lambda value, byte: value ^ byte,
                                               payload, 0)
            if received_crc != calculated_crc:
                send_message({
                    "kind": "warning",
                    "message": (f"stream CRC mismatch: {received_crc:02X}/"
                                f"{calculated_crc:02X}"),
                })
                resyncing = True
                pending_ch1 = []
                pending_ch2 = []
                pending_count = 0
                first_pending_sequence = None
                continue
            resyncing = False

            sequence = int.from_bytes(payload[0:4], "big")
            fs = int.from_bytes(payload[4:8], "big")
            count = int.from_bytes(payload[8:10], "big")
            if expected_sequence is not None and sequence != expected_sequence:
                send_message({
                    "kind": "warning",
                    "message": (f"ADC sample gap: expected {expected_sequence}, "
                                f"got {sequence} ({sequence - expected_sequence:+d} samples)"),
                })
                pending_ch1 = []
                pending_ch2 = []
                pending_count = 0
                first_pending_sequence = None
            expected_sequence = sequence + count

            if header[2] == 0x04:
                values = np.frombuffer(payload[10:], dtype=np.uint8)
                values = values.reshape(-1, 3).astype(np.uint32)
                packed = ((values[:, 0] << 16) |
                          (values[:, 1] << 8) | values[:, 2])
                ch1_raw = ((packed >> 12) & 0x0FFF).astype(np.uint16)
                ch2_raw = (packed & 0x0FFF).astype(np.uint16)
            else:
                raw = np.frombuffer(payload[10:], dtype=">u2").copy()
                ch1_raw = raw[0::2]
                ch2_raw = raw[1::2]
            if first_pending_sequence is None:
                first_pending_sequence = sequence
            pending_ch1.append(ch1_raw)
            pending_ch2.append(ch2_raw)
            pending_count += count
            if pending_count >= UI_BLOCK_SAMPLES:
                send_message({
                    "kind": "capture",
                    "capture": {
                        "ch1_raw": np.concatenate(pending_ch1),
                        "ch2_raw": np.concatenate(pending_ch2),
                        "device_result": {"fs_actual": float(fs)},
                        "sequence": first_pending_sequence,
                        "streaming": True,
                    },
                })
                pending_ch1 = []
                pending_ch2 = []
                pending_count = 0
                first_pending_sequence = None
    except Exception as exc:
        try:
            send_message({"kind": "error", "message": str(exc)})
        except Exception:
            pass
        return 1
    finally:
        connection.close()
        output_socket.close()


if __name__ == "__main__":
    raise SystemExit(main())
