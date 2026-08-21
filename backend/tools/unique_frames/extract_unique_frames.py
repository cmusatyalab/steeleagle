#!/usr/bin/env python3
"""Extract frames from one or more videos and keep only perceptually unique ones."""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import imagehash
from PIL import Image

HASH_ALGOS = {
    "phash": imagehash.phash,
    "dhash": imagehash.dhash,
    "ahash": imagehash.average_hash,
    "whash": imagehash.whash,
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, help="Input video file, or a directory of .mp4 files"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Output directory for unique frames",
    )
    parser.add_argument(
        "--fps", type=float, default=1, help="Frames per second to extract (default: 1)"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=5,
        help="Max Hamming distance to consider a frame a duplicate (default: 5)",
    )
    parser.add_argument(
        "--hash-algo",
        choices=HASH_ALGOS,
        default="phash",
        help="Perceptual hash algorithm (default: phash)",
    )
    return parser.parse_args()


def resolve_video_paths(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        videos = sorted(p for p in input_path.iterdir() if p.suffix.lower() == ".mp4")
        if not videos:
            sys.exit(f"Error: no .mp4 files found in directory: {input_path}")
        return videos

    if input_path.is_file():
        return [input_path]

    sys.exit(f"Error: input path not found: {input_path}")


def check_ffmpeg():
    if shutil.which("ffmpeg") is None:
        sys.exit("Error: ffmpeg not found on PATH. Please install ffmpeg.")


def _parse_rate(rate_str: str) -> float | None:
    num, _, denom = rate_str.partition("/")
    try:
        if denom:
            denom_val = float(denom)
            return float(num) / denom_val if denom_val else None
        return float(num)
    except ValueError:
        return None


def get_source_frame_count(input_path: Path) -> int | None:
    """Best-effort count of frames in the source video, via ffprobe."""
    if shutil.which("ffprobe") is None:
        return None

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=nb_frames,r_frame_rate,avg_frame_rate,duration",
        "-of",
        "default=noprint_wrappers=1",
        str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None

    fields = dict(
        line.split("=", 1) for line in result.stdout.strip().splitlines() if "=" in line
    )

    nb_frames_str = fields.get("nb_frames", "")
    if nb_frames_str.isdigit():
        return int(nb_frames_str)

    frame_rate = _parse_rate(fields.get("avg_frame_rate", "")) or _parse_rate(
        fields.get("r_frame_rate", "")
    )
    try:
        duration = float(fields.get("duration", ""))
    except ValueError:
        return None
    if frame_rate:
        return round(duration * frame_rate)
    return None


def extract_frames(input_path: Path, frames_dir: Path, fps: float):
    frames_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        f"fps={fps}",
        str(frames_dir / "frame_%06d.png"),
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(f"Error: ffmpeg exited with code {result.returncode}")


def filter_unique_frames(
    frames_dir: Path, output_dir: Path, prefix: str, hash_func, threshold: int
):
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_paths = sorted(frames_dir.glob("frame_*.png"))
    if not frame_paths:
        sys.exit("Error: no frames were extracted from the input video.")

    kept_hashes = []
    unique_count = 0
    for i, frame_path in enumerate(frame_paths, start=1):
        with Image.open(frame_path) as img:
            frame_hash = hash_func(img)

        min_distance = min((frame_hash - kept for kept in kept_hashes), default=None)
        is_duplicate = min_distance is not None and min_distance <= threshold

        if not is_duplicate:
            kept_hashes.append(frame_hash)
            unique_count += 1
            shutil.copy2(frame_path, output_dir / f"{prefix}_{frame_path.name}")

        print(
            f"\r  Processed {i}/{len(frame_paths)} frames, {unique_count} unique",
            end="",
            flush=True,
        )

    print()
    return len(frame_paths), unique_count


def process_video(
    video_path: Path, output_dir: Path, hash_func, fps: float, threshold: int
):
    source_frame_count = get_source_frame_count(video_path)

    with tempfile.TemporaryDirectory(prefix="frames_") as tmp:
        frames_dir = Path(tmp)
        extract_frames(video_path, frames_dir, fps)
        total, unique = filter_unique_frames(
            frames_dir, output_dir, video_path.stem, hash_func, threshold
        )

    return source_frame_count, total, unique


def main():
    args = parse_args()
    check_ffmpeg()

    video_paths = resolve_video_paths(args.input)
    hash_func = HASH_ALGOS[args.hash_algo]

    results = []
    for i, video_path in enumerate(video_paths, start=1):
        print(
            f"[{i}/{len(video_paths)}] {video_path.name}: extracting frames at {args.fps} fps..."
        )
        source_frame_count, total, unique = process_video(
            video_path, args.output, hash_func, args.fps, args.threshold
        )
        results.append((video_path.name, source_frame_count, total, unique))

        print(
            f"  Summary: {source_frame_count if source_frame_count is not None else 'unknown'} source frames, "
            f"{total} extracted, {unique} unique kept"
        )

    if len(results) > 1:
        total_source = sum(r[1] for r in results if r[1] is not None)
        total_extracted = sum(r[2] for r in results)
        total_unique = sum(r[3] for r in results)
        print("\nOverall summary:")
        print(f"  Videos processed:      {len(results)}")
        print(f"  Source video frames:   {total_source}")
        print(f"  Frames extracted:      {total_extracted} (at {args.fps} fps)")
        print(
            f"  Unique frames kept:    {total_unique} ({args.hash_algo}, threshold={args.threshold})"
        )

    print(f"  Output directory:      {args.output}")


if __name__ == "__main__":
    main()
