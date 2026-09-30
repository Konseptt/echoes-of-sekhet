#!/usr/bin/env python3
"""
Generate simulated 16-channel EEG stream over LSL for testing.

Usage:
  python scripts/simulate_eeg_stream.py
"""
import time
import math
import random
import sys

try:
    from pylsl import StreamInfo, StreamOutlet
except ImportError:
    print("pylsl not found. Run: pip install pylsl", file=sys.stderr)
    sys.exit(1)

STREAM_NAME = "actiCHamp_Simulated"
STREAM_TYPE = "EEG"
CHANNEL_COUNT = 16
SAMPLING_RATE = 500.0

CH_NAMES = [
    "Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4",
    "O1", "O2", "F7", "F8", "T7", "T8", "P7", "P8"
]

def main():
    info = StreamInfo(
        name=STREAM_NAME,
        type=STREAM_TYPE,
        channel_count=CHANNEL_COUNT,
        nominal_srate=SAMPLING_RATE,
        channel_format="float32",
        source_id="simulated-actichamp-01"
    )

    channels_node = info.desc().append_child("channels")
    for name in CH_NAMES:
        ch = channels_node.append_child("channel")
        ch.append_child_value("label", name)
        ch.append_child_value("unit", "microvolts")
        ch.append_child_value("type", "EEG")

    outlet = StreamOutlet(info, chunk_size=32, max_buffered=360)
    print(f"[sim] broadcasting EEG: {STREAM_NAME} ({CHANNEL_COUNT} channels @ {SAMPLING_RATE:.0f} Hz)")

    dt = 1.0 / SAMPLING_RATE
    start_time = time.perf_counter()
    sample_index = 0

    try:
        while True:
            chunk = []
            for _ in range(10):
                t = sample_index * dt
                sample = []
                for i in range(CHANNEL_COUNT):
                    freq1 = 9.0 + (i % 3)
                    freq2 = 18.0 + (i % 4)
                    val = (
                        15.0 * math.sin(2 * math.pi * freq1 * t + i * 0.5)
                        + 6.0 * math.sin(2 * math.pi * freq2 * t + i * 1.2)
                        + random.gauss(0, 4.0)
                    )
                    sample.append(val)
                chunk.append(sample)
                sample_index += 1

            outlet.push_chunk(chunk)

            expected_time = start_time + (sample_index * dt)
            sleep_sec = expected_time - time.perf_counter()
            if sleep_sec > 0:
                time.sleep(sleep_sec)
    except KeyboardInterrupt:
        print("\n[sim] stopped simulated EEG stream.")

if __name__ == "__main__":
    main()
