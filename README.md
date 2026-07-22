# Focus-16

Focus-16 is an evidence-informed audio prototype designed for focused work. It generates a predictable, lyric-free instrumental bed with low harmonic variation and an experimental 16 Hz amplitude modulation applied only to the 200–1000 Hz musical layer.

This project is experimental audio software, not a medical treatment or a scientifically established focus intervention. The evidence below does not support a guaranteed improvement, a universal benefit, or a “2× focus” claim.

## What the project provides

- A deterministic Python generator for stereo PCM WAV audio.
- A release builder that creates a loudness-normalized WAV plus FLAC and MP3 encodings.
- Automated verification for duration, channel layout, clipping, spectral energy, and the intended mid-band modulation peak.
- Reproducible metadata and release hashes in JSON format.
- Pre-rendered FLAC and MP3 examples for Focus-16.

## Design

| Parameter | Default | Purpose |
| --- | ---: | --- |
| Tempo | 120 BPM | Provides a clear, predictable rhythmic grid. |
| Musical center | C major | Keeps the harmonic language simple and stable. |
| Modulation | 16 Hz at 28% depth | Experimental parameter applied only to the 200–1000 Hz musical layer. |
| Low layer | Below 200 Hz | Provides an unmodulated bass foundation. |
| High layer | Up to 6 kHz | Adds a quiet, unmodulated shimmer without broadband noise. |
| Output | 48 kHz, stereo | Produces a distribution-ready audio format. |
| Loudness target | −23 LUFS integrated | Used by the two-pass release normalization. |
| Default duration | 10 minutes | Keeps the default render practical while allowing custom durations. |

The generator deliberately excludes speech, lyrics, abrupt section changes, binaural tones, and broadband white or pink noise. The 16 Hz modulation is synchronized to the musical timing grid, but it should be treated as a testable design choice rather than a proven mechanism.

## Repository layout

| File | Description |
| --- | --- |
| `generate_focus_audio.py` | Synthesizes the deterministic raw WAV prototype. |
| `build_release.py` | Generates the normalized WAV, FLAC, MP3, and JSON release report; requires FFmpeg. |
| `verify_focus_audio.py` | Analyzes the rendered WAV and checks the design constraints. |
| `tests/test_generator.py` | Unit tests for rendering, modulation, and configuration validation. |
| `Focus-16-v0.1.flac` | Pre-rendered lossless example. |
| `Focus-16-v0.1.mp3` | Pre-rendered 192 kbps example. |
| `Focus-16-v0.1-report.json` | Release metadata, verification results, and SHA-256 hashes. |
| `EVIDENCE.md` | Legacy pointer to the evidence section in this README. |
| `LICENSE` | MIT License for the project. |

## Requirements

- Python 3.10 or newer is recommended.
- NumPy 2.x or newer and SciPy 1.13 or newer.
- FFmpeg is required only for `build_release.py`.

Install the Python dependencies with:

```bash
python -m pip install -r requirements.txt
```

## Usage

Generate a raw WAV and optional JSON metadata:

```bash
python generate_focus_audio.py \
  --output build/focus-16-raw.wav \
  --metadata build/raw-report.json
```

Verify a rendered WAV:

```bash
python verify_focus_audio.py build/focus-16-raw.wav
```

Build the normalized distribution files:

```bash
python build_release.py --output-dir build --minutes 10
```

Run the test suite:

```bash
python -m unittest discover -s tests -v
```

The generator accepts custom duration, sample rate, tempo, modulation frequency, modulation depth, and random seed values. The current synthesis path is deterministic; the seed is retained in the configuration and report for reproducibility.

## Verification model

`verify_focus_audio.py` reads a window from the rendered WAV and checks:

1. Stereo channel count, sample rate, frame count, and duration.
2. Peak level below digital clipping.
3. The dominant envelope frequency in the 200–1000 Hz band, expected at 16 Hz by default.
4. The proportion of spectral energy below the design ceiling of 6 kHz.

The release report records these measurements along with the generated file sizes and SHA-256 hashes. Verification confirms that the file matches the intended signal design; it does not demonstrate that the audio improves attention or productivity.

## Evidence and design rationale

The design is based on converging considerations from broad reviews and direct parametric studies. These references motivate conservative audio choices; they do not establish that Focus-16 itself produces a particular cognitive outcome.

1. A systematic review covering 95 papers and 154 experiments reported that background music was often ineffective or detrimental for memory, language, and demanding tasks, with lyrics tending to be more disruptive. This motivates a simple, predictable, lyric-free design. [DOI: 10.1177/20592043221134392](https://doi.org/10.1177/20592043221134392)

2. A 2025 study reported mood and processing-speed benefits for continuous “work flow” music with a pronounced rhythm, simple tonal structure, and no lyrics. The study’s funding by the music provider was treated as a relevant limitation. [DOI: 10.1371/journal.pone.0316047](https://doi.org/10.1371/journal.pone.0316047)

3. A parametric study identified 16 Hz amplitude modulation added to the 200–1000 Hz layer of 120 BPM music as a leading candidate, particularly among participants reporting greater attention difficulty. Because the study involved Brain.fm employees and a subsequently corrected conflict-of-interest disclosure, Focus-16 uses 16 Hz as an experimental parameter, not as an established result. [DOI: 10.1038/s42003-024-07026-3](https://doi.org/10.1038/s42003-024-07026-3)

4. A 2024 meta-analysis found a small benefit from white or pink noise in ADHD or high-symptom groups (*g* = 0.249) and a small detriment in typical-attention groups (*g* = −0.212). This is why broadband noise is excluded from the universal prototype. [DOI: 10.1016/j.jaac.2023.12.014](https://doi.org/10.1016/j.jaac.2023.12.014)

5. A systematic review of binaural entrainment included 14 EEG studies with inconsistent results: five supported the hypothesis, eight were contradictory, and one was mixed. Binaural tones are therefore excluded from this prototype. [DOI: 10.1371/journal.pone.0286023](https://doi.org/10.1371/journal.pone.0286023)

## Limitations

- The prototype makes no clinical, therapeutic, or guaranteed productivity claim.
- Any effect is expected to be small, task-dependent, and person-dependent.
- The source studies do not validate this exact synthesis, mix, or release format.
- Listen at a comfortable level and stop if the modulation or audio causes discomfort.

## License

This project is released under the [MIT License](LICENSE). You may use, copy, modify, publish, distribute, sublicense, and sell the software, subject to the license terms.
