#!/usr/bin/env python3
"""Generate the evidence-informed Focus-16 prototype.

This is an audio prototype, not a treatment.  The design intentionally uses:

* a predictable 120 BPM instrumental bed;
* low harmonic and rhythmic complexity;
* 16 Hz amplitude modulation restricted to the 200-1000 Hz musical layer;
* no speech, lyrics, binaural beat, or broadband noise.

The generator is deterministic for a given seed and writes stereo PCM WAV.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class FocusAudioConfig:
    bpm: float = 120.0
    modulation_hz: float = 16.0
    modulation_depth: float = 0.28
    modulation_low_hz: float = 200.0
    modulation_high_hz: float = 1000.0
    sample_rate: int = 48_000
    minutes: float = 10.0
    seed: int = 20260722
    chord_seconds: float = 16.0
    chord_crossfade_seconds: float = 2.0
    fade_seconds: float = 8.0

    def validate(self) -> None:
        if not 60 <= self.bpm <= 180:
            raise ValueError("BPM must be between 60 and 180")
        if not 1 <= self.modulation_hz <= 40:
            raise ValueError("Modulation rate must be between 1 and 40 Hz")
        if not 0 <= self.modulation_depth <= 0.60:
            raise ValueError("Modulation depth must be between 0 and 0.60")
        if not 8_000 <= self.sample_rate <= 192_000:
            raise ValueError("Sample rate must be between 8000 and 192000")
        if self.minutes <= 0:
            raise ValueError("Duration must be positive")
        if self.modulation_low_hz >= self.modulation_high_hz:
            raise ValueError("Modulation band is invalid")
        if self.modulation_high_hz >= self.sample_rate / 2:
            raise ValueError("Modulation band exceeds Nyquist")
        if not 0 <= self.chord_crossfade_seconds < self.chord_seconds / 2:
            raise ValueError("Chord crossfade is invalid")


# All mid-layer fundamentals and included harmonics remain in 200-1000 Hz.
CHORDS_MIDI: tuple[tuple[int, ...], ...] = (
    (60, 64, 67, 71, 74),       # Cmaj9
    (60, 65, 69, 72, 76),       # Fmaj9/C
    (60, 64, 67, 71, 76),       # Cmaj7(add 13)
    (60, 62, 67, 69, 74),       # Gsus/C, all notes from C major
)
LOW_ROOTS_MIDI: tuple[int, ...] = (36, 41, 36, 43)
ARP_PATTERN: tuple[int, ...] = (0, 2, 1, 3, 2, 4, 3, 1)


def midi_hz(note: np.ndarray | float | int) -> np.ndarray:
    return 440.0 * np.power(2.0, (np.asarray(note, dtype=np.float64) - 69.0) / 12.0)


def raised_cosine(value: np.ndarray) -> np.ndarray:
    clipped = np.clip(value, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * clipped)


def chord_weights(t: np.ndarray, config: FocusAudioConfig) -> np.ndarray:
    """Return smooth weights for the four-chord cycle."""
    segment = np.floor(t / config.chord_seconds).astype(np.int64)
    phase = np.mod(t, config.chord_seconds)
    fade_start = config.chord_seconds - config.chord_crossfade_seconds
    next_weight = raised_cosine(
        (phase - fade_start) / config.chord_crossfade_seconds
    )
    current_weight = 1.0 - next_weight
    weights = np.zeros((len(CHORDS_MIDI), t.size), dtype=np.float64)
    current = np.mod(segment, len(CHORDS_MIDI))
    following = np.mod(segment + 1, len(CHORDS_MIDI))
    for chord_index in range(len(CHORDS_MIDI)):
        weights[chord_index] += (current == chord_index) * current_weight
        weights[chord_index] += (following == chord_index) * next_weight
    return weights


def oscillator(frequency: float, t: np.ndarray, phase: float = 0.0) -> np.ndarray:
    return np.sin(2.0 * np.pi * frequency * t + phase)


def build_mid_layer(
    t: np.ndarray,
    weights: np.ndarray,
    config: FocusAudioConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Create the 200-1000 Hz musical stem, then apply 16 Hz AM."""
    left = np.zeros_like(t)
    right = np.zeros_like(t)

    for chord_index, notes in enumerate(CHORDS_MIDI):
        chord_weight = weights[chord_index]
        for note_index, midi_note in enumerate(notes):
            frequency = float(midi_hz(midi_note))
            pan = 0.22 + 0.56 * (note_index / (len(notes) - 1))
            left_gain = math.cos(pan * math.pi / 2.0)
            right_gain = math.sin(pan * math.pi / 2.0)
            phase = chord_index * 0.41 + note_index * 0.73

            # Tiny opposing detune creates width without chorus-like movement.
            left_tone = oscillator(frequency * 0.9997, t, phase)
            right_tone = oscillator(frequency * 1.0003, t, phase)
            tone_gain = 0.014 / math.sqrt(len(notes))
            left += chord_weight * left_tone * tone_gain * left_gain
            right += chord_weight * right_tone * tone_gain * right_gain

            second = frequency * 2.0
            if second <= config.modulation_high_hz:
                harmonic_gain = tone_gain * 0.22
                left += chord_weight * oscillator(second, t, phase + 0.3) * harmonic_gain * left_gain
                right += chord_weight * oscillator(second, t, phase + 0.5) * harmonic_gain * right_gain

    # A simple eighth-note arpeggio gives a clear, predictable 120 BPM grid.
    step_seconds = 30.0 / config.bpm
    step_index = np.floor(t / step_seconds).astype(np.int64)
    step_phase = np.mod(t, step_seconds)
    chord_index = np.mod(np.floor(t / config.chord_seconds).astype(np.int64), len(CHORDS_MIDI))
    pattern_index = np.mod(step_index, len(ARP_PATTERN))
    selected_midi = np.empty(t.size, dtype=np.float64)
    for chord in range(len(CHORDS_MIDI)):
        for pattern_position, note_position in enumerate(ARP_PATTERN):
            mask = (chord_index == chord) & (pattern_index == pattern_position)
            selected_midi[mask] = CHORDS_MIDI[chord][note_position]
    selected_hz = midi_hz(selected_midi)
    attack = 1.0 - np.exp(-step_phase / 0.012)
    decay = np.exp(-step_phase / 0.115)
    release = raised_cosine((step_seconds - step_phase) / 0.045)
    arp_envelope = attack * decay * release
    arp_phase = 2.0 * np.pi * selected_hz * t
    arp = np.sin(arp_phase) * arp_envelope * 0.025
    pan_motion = 0.5 + 0.16 * np.sin(2.0 * np.pi * t / 32.0)
    left += arp * np.cos(pan_motion * np.pi / 2.0)
    right += arp * np.sin(pan_motion * np.pi / 2.0)

    # Peaks align to the 120 BPM metrical grid: 8 modulation cycles per beat.
    modulation = (
        1.0
        - config.modulation_depth / 2.0
        + config.modulation_depth / 2.0
        * np.cos(2.0 * np.pi * config.modulation_hz * t)
    )
    return left * modulation, right * modulation


def build_low_layer(
    t: np.ndarray,
    weights: np.ndarray,
    config: FocusAudioConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Create an unmodulated bass bed below 200 Hz."""
    bed = np.zeros_like(t)
    for chord_index, root_note in enumerate(LOW_ROOTS_MIDI):
        root = float(midi_hz(root_note))
        weight = weights[chord_index]
        bed += weight * oscillator(root, t, chord_index * 0.2) * 0.030
        bed += weight * oscillator(root * 2.0, t, chord_index * 0.2 + 0.4) * 0.009

    beat_seconds = 60.0 / config.bpm
    beat_index = np.floor(t / beat_seconds).astype(np.int64)
    beat_phase = np.mod(t, beat_seconds)
    active_chord = np.mod(np.floor(t / config.chord_seconds).astype(np.int64), len(CHORDS_MIDI))
    selected_roots = midi_hz(np.take(np.asarray(LOW_ROOTS_MIDI), active_chord))
    bass_env = (1.0 - np.exp(-beat_phase / 0.010)) * np.exp(-beat_phase / 0.160)
    bass_pulse = np.sin(2.0 * np.pi * selected_roots * t) * bass_env * 0.065

    # Soft kick on beats 1 and 3. The chirp stays below 80 Hz.
    kick_mask = (np.mod(beat_index, 4) == 0) | (np.mod(beat_index, 4) == 2)
    kick_env = np.exp(-beat_phase / 0.095) * kick_mask
    chirp_phase = 2.0 * np.pi * (68.0 * beat_phase - 30.0 * beat_phase**2)
    kick = np.sin(chirp_phase) * kick_env * 0.085
    mono = bed + bass_pulse + kick
    return mono * 0.707, mono * 0.707


def build_high_layer(t: np.ndarray, config: FocusAudioConfig) -> tuple[np.ndarray, np.ndarray]:
    """Create a quiet, unmodulated shimmer below 6 kHz."""
    step_seconds = 30.0 / config.bpm
    step_index = np.floor(t / step_seconds).astype(np.int64)
    step_phase = np.mod(t, step_seconds)
    offbeat = np.mod(step_index, 2) == 1
    envelope = np.exp(-step_phase / 0.032) * offbeat
    frequencies = (1450.0, 2380.0, 3570.0, 4920.0)
    shimmer_left = np.zeros_like(t)
    shimmer_right = np.zeros_like(t)
    for index, frequency in enumerate(frequencies):
        gain = 0.0033 / (1.0 + index * 0.32)
        phase = 0.9 * index
        tone = oscillator(frequency, t, phase) * envelope * gain
        if index % 2:
            shimmer_left += tone * 0.55
            shimmer_right += tone
        else:
            shimmer_left += tone
            shimmer_right += tone * 0.55
    return shimmer_left, shimmer_right


def render_chunk(
    frame_start: int,
    frame_count: int,
    total_frames: int,
    config: FocusAudioConfig,
) -> np.ndarray:
    indices = np.arange(frame_start, frame_start + frame_count, dtype=np.float64)
    t = indices / config.sample_rate
    weights = chord_weights(t, config)

    low_left, low_right = build_low_layer(t, weights, config)
    mid_left, mid_right = build_mid_layer(t, weights, config)
    high_left, high_right = build_high_layer(t, config)

    macro = 0.96 + 0.04 * np.sin(2.0 * np.pi * t / 64.0 - np.pi / 2.0)
    left = (low_left + mid_left + high_left) * macro
    right = (low_right + mid_right + high_right) * macro

    fade_frames = max(1, int(config.fade_seconds * config.sample_rate))
    fade_in = raised_cosine(indices / fade_frames)
    frames_remaining = total_frames - indices - 1
    fade_out = raised_cosine(frames_remaining / fade_frames)
    fade = np.minimum(fade_in, fade_out)

    # Gentle saturation catches coincident transients without hard clipping.
    stereo = np.column_stack((left, right)) * fade[:, None]
    stereo = np.tanh(stereo * 1.35) / np.tanh(1.35)
    stereo *= 0.82
    return np.clip(stereo, -0.98, 0.98)


def generate_wav(output: Path, config: FocusAudioConfig) -> dict[str, float | int | str]:
    config.validate()
    output.parent.mkdir(parents=True, exist_ok=True)
    total_frames = int(round(config.minutes * 60.0 * config.sample_rate))
    chunk_frames = config.sample_rate * 4
    peak = 0.0
    sum_squares = 0.0
    sample_count = 0

    with wave.open(str(output), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(config.sample_rate)

        for frame_start in range(0, total_frames, chunk_frames):
            frame_count = min(chunk_frames, total_frames - frame_start)
            chunk = render_chunk(frame_start, frame_count, total_frames, config)
            peak = max(peak, float(np.max(np.abs(chunk))))
            sum_squares += float(np.sum(chunk * chunk))
            sample_count += int(chunk.size)
            pcm = np.rint(chunk * 32767.0).astype("<i2", copy=False)
            wav_file.writeframes(pcm.tobytes())

    rms = math.sqrt(sum_squares / max(sample_count, 1))
    return {
        "output": str(output),
        "frames": total_frames,
        "sample_rate": config.sample_rate,
        "channels": 2,
        "seconds": total_frames / config.sample_rate,
        "peak_linear": peak,
        "rms_linear": rms,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the Focus-16 stereo WAV prototype.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minutes", type=float, default=10.0)
    parser.add_argument("--sample-rate", type=int, default=48_000)
    parser.add_argument("--bpm", type=float, default=120.0)
    parser.add_argument("--modulation-hz", type=float, default=16.0)
    parser.add_argument("--modulation-depth", type=float, default=0.28)
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--metadata", type=Path, help="Optional path for a JSON report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = FocusAudioConfig(
        bpm=args.bpm,
        modulation_hz=args.modulation_hz,
        modulation_depth=args.modulation_depth,
        sample_rate=args.sample_rate,
        minutes=args.minutes,
        seed=args.seed,
    )
    try:
        metrics = generate_wav(args.output, config)
    except ValueError as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 2

    report = {
        "prototype": "Focus-16",
        "claim": "experimental; no 2x focus claim",
        "config": asdict(config),
        "render": metrics,
    }
    if args.metadata:
        args.metadata.parent.mkdir(parents=True, exist_ok=True)
        args.metadata.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
