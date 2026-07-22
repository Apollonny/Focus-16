#!/usr/bin/env python3
"""Build normalized WAV, FLAC, and MP3 releases for Focus-16."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import asdict
from pathlib import Path

from generate_focus_audio import FocusAudioConfig, generate_wav
from verify_focus_audio import verify


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


def extract_json(stderr: str) -> dict[str, str]:
    matches = re.findall(r"\{\s*\"input_i\".*?\}", stderr, flags=re.DOTALL)
    if not matches:
        raise RuntimeError("FFmpeg loudnorm report could not be parsed")
    return json.loads(matches[-1])


def two_pass_loudnorm(source: Path, destination: Path, sample_rate: int) -> dict[str, str]:
    target = "loudnorm=I=-23:TP=-2:LRA=7"
    first = run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(source),
        "-af", f"{target}:print_format=json", "-f", "null", "-",
    ])
    measured = extract_json(first.stderr)
    second_filter = (
        f"{target}"
        f":measured_I={measured['input_i']}"
        f":measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}"
        f":measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}"
        ":linear=true:print_format=json"
    )
    second = run([
        "ffmpeg", "-hide_banner", "-nostats", "-y", "-i", str(source),
        "-af", second_filter, "-ar", str(sample_rate), "-c:a", "pcm_s16le",
        str(destination),
    ])
    return extract_json(second.stderr)


def encode(source: Path, destination: Path, codec_args: list[str]) -> None:
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
        "-map_metadata", "-1",
        "-metadata", "title=Focus-16",
        "-metadata", "artist=Evidence Focus Audio",
        "-metadata", "comment=Experimental prototype; no 2x focus claim",
        *codec_args,
        str(destination),
    ])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("build"))
    parser.add_argument("--minutes", type=float, default=10.0)
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    config = FocusAudioConfig(minutes=args.minutes)
    raw_path = output_dir / "focus-16-raw.wav"
    wav_path = output_dir / "Focus-16.wav"
    flac_path = output_dir / "Focus-16.flac"
    mp3_path = output_dir / "Focus-16.mp3"

    render = generate_wav(raw_path, config)
    loudness = two_pass_loudnorm(raw_path, wav_path, config.sample_rate)
    encode(wav_path, flac_path, ["-c:a", "flac", "-compression_level", "8"])
    encode(wav_path, mp3_path, ["-c:a", "libmp3lame", "-b:a", "192k"])
    verification = verify(wav_path)

    report = {
        "prototype": "Focus-16",
        "claim": "experimental; no 2x focus claim",
        "config": asdict(config),
        "render": render,
        "loudnorm": loudness,
        "verification": verification,
        "files": {
            path.name: {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in (wav_path, flac_path, mp3_path)
        },
    }
    report_path = output_dir / "Focus-16-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
