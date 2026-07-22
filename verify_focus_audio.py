#!/usr/bin/env python3
"""Verify duration, peak, spectrum, and the intended 16 Hz mid-band modulation."""

from __future__ import annotations

import argparse
import json
import math
import wave
from pathlib import Path

import numpy as np
from scipy import signal


def read_window(path: Path, start_seconds: float, seconds: float) -> tuple[np.ndarray, int, int, float]:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        total_frames = wav_file.getnframes()
        if sample_width != 2:
            raise ValueError("Only 16-bit PCM WAV is supported")
        requested_count = min(int(seconds * sample_rate), total_frames)
        start = min(
            int(start_seconds * sample_rate),
            max(0, total_frames - requested_count),
        )
        count = min(requested_count, total_frames - start)
        wav_file.setpos(start)
        data = np.frombuffer(wav_file.readframes(count), dtype="<i2").astype(np.float64)
    data = data.reshape(-1, channels) / 32768.0
    return data, sample_rate, total_frames, total_frames / sample_rate


def verify(path: Path, expected_modulation: float = 16.0) -> dict[str, float | int | bool | str]:
    data, sample_rate, total_frames, duration = read_window(path, 30.0, 45.0)
    mono = np.mean(data, axis=1)
    peak = float(np.max(np.abs(data)))
    rms = float(np.sqrt(np.mean(data * data)))

    # Isolate the deliberately modulated musical band and analyze its envelope.
    sos = signal.butter(6, [200.0, 1000.0], btype="bandpass", fs=sample_rate, output="sos")
    mid = signal.sosfiltfilt(sos, mono)
    envelope = np.abs(signal.hilbert(mid))
    envelope -= np.mean(envelope)
    frequencies, power = signal.periodogram(envelope, fs=sample_rate, window="hann")
    modulation_mask = (frequencies >= 10.0) & (frequencies <= 22.0)
    modulation_peak_hz = float(frequencies[modulation_mask][np.argmax(power[modulation_mask])])

    # Check how much signal energy remains below the design ceiling of 6 kHz.
    spectrum_f, spectrum_p = signal.periodogram(mono, fs=sample_rate, window="hann")
    total_energy = float(np.sum(spectrum_p))
    below_6k = float(np.sum(spectrum_p[spectrum_f <= 6000.0]))
    energy_below_6k = below_6k / max(total_energy, np.finfo(float).eps)

    return {
        "path": str(path),
        "sample_rate": sample_rate,
        "channels": int(data.shape[1]),
        "frames": total_frames,
        "duration_seconds": duration,
        "peak_linear": peak,
        "rms_linear": rms,
        "midband_modulation_peak_hz": modulation_peak_hz,
        "modulation_matches": math.isclose(modulation_peak_hz, expected_modulation, abs_tol=0.10),
        "energy_below_6khz_ratio": energy_below_6k,
        "no_clipping": peak < 0.999,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--expected-modulation", type=float, default=16.0)
    args = parser.parse_args()
    result = verify(args.path, args.expected_modulation)
    print(json.dumps(result, indent=2))
    return 0 if result["modulation_matches"] and result["no_clipping"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
