"""Tests for extracting metadata from the Anafi's recordings.

These read a real recording, given by ANAFI_RECORDING (by default one on the
developer's machine), and are skipped without one: recordings are gigabytes.
"""

import csv
import io
import json
import os
from datetime import datetime

import pytest

import anafi_blackbox as blackbox

RECORDING = os.environ.get(
    "ANAFI_RECORDING", os.path.expanduser("~/Videos/P5770841.MP4")
)
needs_recording = pytest.mark.skipif(
    not os.path.exists(RECORDING), reason=f"no Anafi recording at {RECORDING}"
)


@needs_recording
def test_every_frame_has_metadata():
    with blackbox.BlackboxReader(RECORDING) as reader:
        frames = list(reader.frames())
    assert len(frames) == len(reader)
    assert [f.frame for f in frames] == list(range(len(frames)))
    assert all(a.video_time < b.video_time for a, b in zip(frames, frames[1:]))
    located = [f for f in frames if f.latitude is not None]
    assert located
    for f in located:
        assert -90 <= f.latitude <= 90 and -180 <= f.longitude <= 180
        assert f.altitude_amsl is not None
        assert f.satellites > 0


@needs_recording
def test_every_nth_frame():
    with blackbox.BlackboxReader(RECORDING) as reader:
        frames = list(reader.frames(every=1000))
        count = len(reader)
    assert [f.frame for f in frames] == list(range(0, count, 1000))


@needs_recording
def test_raw_has_decoded_fields():
    with blackbox.BlackboxReader(RECORDING) as reader:
        frame = next(reader.frames(raw=True))
    assert "location" in frame.raw or "ground_distance" in frame.raw


@needs_recording
def test_csv_and_jsonl_agree():
    with blackbox.BlackboxReader(RECORDING) as reader:
        frames = list(reader.frames(every=5000))
    csv_out, jsonl_out = io.StringIO(), io.StringIO()
    blackbox.write_csv(
        blackbox.rows(frames, blackbox.COLUMNS), blackbox.COLUMNS, csv_out
    )
    blackbox.write_jsonl(blackbox.rows(frames, blackbox.COLUMNS), jsonl_out)
    rows = list(csv.DictReader(io.StringIO(csv_out.getvalue())))
    lines = [json.loads(line) for line in jsonl_out.getvalue().splitlines()]
    assert len(rows) == len(lines) == len(frames)
    for row, line in zip(rows, lines):
        assert int(row["frame"]) == line["frame"]
        assert row["latitude"] == (
            "" if line["latitude"] is None else str(line["latitude"])
        )
        assert "raw" not in line


def test_not_a_recording(tmp_path):
    path = tmp_path / "junk.mp4"
    path.write_bytes(b"not an mp4")
    with pytest.raises(blackbox.BlackboxError):
        blackbox.BlackboxReader(str(path))


def test_missing_file(tmp_path):
    with pytest.raises(blackbox.BlackboxError):
        blackbox.BlackboxReader(str(tmp_path / "missing.mp4"))


@needs_recording
def test_utc_time_is_start_plus_video_time():
    with blackbox.BlackboxReader(RECORDING) as reader:
        frames = list(reader.frames(every=1000))
        start = reader.start_time
    assert start is not None and start.tzinfo is not None
    for f in frames:
        offset = datetime.fromisoformat(f.utc_time) - start
        assert abs(offset.total_seconds() - f.video_time) < 0.001


def run(tmp_path, *args):
    out = tmp_path / "out"
    blackbox.main([RECORDING, "-o", str(out), *args])
    return out.read_text()


@needs_recording
def test_columns_in_given_order(tmp_path):
    text = run(
        tmp_path,
        "-n",
        "5000",
        "-c",
        "longitude,utc_time,speed.north,lfic.target_location.latitude",
    )
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == [
        "longitude",
        "utc_time",
        "speed.north",
        "lfic.target_location.latitude",
    ]
    assert len(rows) > 2
    for row in rows[1:]:
        assert float(row[0]) < 0 and row[1] and float(row[2]) == float(row[2])


@needs_recording
def test_columns_jsonl_uses_dotted_keys(tmp_path):
    text = run(
        tmp_path, "-n", "5000", "-f", "jsonl", "-c", "frame,speed,battery_percentage"
    )
    line = json.loads(text.splitlines()[0])
    assert list(line) == ["frame", "speed", "battery_percentage"]
    assert set(line["speed"]) == {"north", "east", "down"}


@needs_recording
def test_unknown_column_fails(tmp_path):
    with pytest.raises(SystemExit) as e:
        run(tmp_path, "-n", "5000", "-c", "latitude,sped.north")
    assert "sped.north" in str(e.value)


@needs_recording
def test_list_columns(tmp_path):
    names = [line.split()[0] for line in run(tmp_path, "--list-columns").splitlines()]
    assert names[: len(blackbox.COLUMNS)] == blackbox.COLUMNS
    assert "speed.north" in names and "location.latitude" in names


@pytest.mark.parametrize(
    "args",
    [
        ["-c", "latitude,,longitude"],
        ["-c", "frame,frame"],
        ["--raw", "-f", "jsonl", "-c", "frame"],
    ],
)
def test_bad_columns_arguments(args):
    with pytest.raises(SystemExit):
        blackbox.main(["unused.mp4", *args])
