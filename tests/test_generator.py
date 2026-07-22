from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np
from scipy import signal

from generate_focus_audio import FocusAudioConfig, generate_wav


class FocusAudioGeneratorTests(unittest.TestCase):
    def test_short_render_has_expected_shape_and_no_clipping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "short.wav"
            config = FocusAudioConfig(minutes=0.05, sample_rate=16_000, fade_seconds=0.25)
            metrics = generate_wav(output, config)
            with wave.open(str(output), "rb") as wav_file:
                self.assertEqual(wav_file.getnchannels(), 2)
                self.assertEqual(wav_file.getframerate(), 16_000)
                self.assertEqual(wav_file.getnframes(), 48_000)
                samples = np.frombuffer(wav_file.readframes(wav_file.getnframes()), dtype="<i2")
            self.assertLess(np.max(np.abs(samples)), 32767)
            self.assertGreater(metrics["rms_linear"], 0)

    def test_midband_envelope_contains_16_hz_peak(self) -> None:
        sample_rate = 16_000
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "modulation.wav"
            config = FocusAudioConfig(minutes=0.20, sample_rate=sample_rate, fade_seconds=0.25)
            generate_wav(output, config)
            with wave.open(str(output), "rb") as wav_file:
                samples = np.frombuffer(wav_file.readframes(wav_file.getnframes()), dtype="<i2")
            mono = samples.reshape(-1, 2).mean(axis=1) / 32768.0
            mono = mono[2 * sample_rate : 10 * sample_rate]
            sos = signal.butter(6, [200, 1000], btype="bandpass", fs=sample_rate, output="sos")
            envelope = np.abs(signal.hilbert(signal.sosfiltfilt(sos, mono)))
            frequencies, power = signal.periodogram(envelope - envelope.mean(), fs=sample_rate)
            mask = (frequencies >= 10) & (frequencies <= 22)
            peak = frequencies[mask][np.argmax(power[mask])]
            self.assertAlmostEqual(float(peak), 16.0, delta=0.15)

    def test_invalid_depth_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FocusAudioConfig(modulation_depth=0.9).validate()


if __name__ == "__main__":
    unittest.main()
