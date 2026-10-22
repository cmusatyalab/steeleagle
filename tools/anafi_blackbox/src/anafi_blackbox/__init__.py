"""Extracts per-frame metadata, such as the drone's GPS location and altitude,
from a video the Anafi recorded to its SD card.

The drone records its video metadata (the same as it streams, see
https://developer.parrot.com/docs/pdraw/video-metadata.html) in a timed
metadata track beside the video, one sample per frame. This reads that track
with libmp4 and decodes each sample with libvideo-metadata, both of which
olympe ships, so no frame is decoded and an hour of video takes seconds.
"""

import argparse
import csv
import ctypes
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import olympe_deps as od


class BlackboxError(Exception):
    pass


@dataclass
class FrameMetadata:
    """The metadata of one frame. Location fields are None when the drone had
    no GPS fix."""

    frame: int
    # Seconds since the start of the video.
    video_time: float
    # When the frame was captured, in ISO 8601: the recording's start, which
    # the MP4 stores only to the second, plus video_time.
    utc_time: str | None
    # Microseconds on the drone's clock.
    frame_timestamp: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    # Meters above mean sea level (EGM96).
    altitude_amsl: float | None = None
    # Meters above the WGS84 ellipsoid; the Anafi records only AMSL.
    altitude_wgs84: float | None = None
    # Meters above the ground, from the drone's height estimate.
    ground_distance: float | None = None
    satellites: int | None = None
    # Every field libvideo-metadata decodes, as its JSON.
    raw: dict | None = None


def _string(pointer):
    return ctypes.string_at(pointer).decode() if pointer else None


def _finite(value):
    return value if math.isfinite(value) else None


class BlackboxReader:
    """Reads the metadata of the frames of the recording at `path`."""

    def __init__(self, path):
        self._demux = od.POINTER_T(od.struct_mp4_demux)()
        res = od.mp4_demux_open(path.encode(), ctypes.byref(self._demux))
        if res < 0:
            raise BlackboxError(f"cannot open {path}: error {res}")
        try:
            self._track = self._metadata_track()
        except BlackboxError:
            self.close()
            raise
        self.start_time = self._start_time()

    def _metadata_track(self):
        for index in range(od.mp4_demux_get_track_count(self._demux)):
            info = od.struct_mp4_track_info()
            if od.mp4_demux_get_track_info(self._demux, index, ctypes.byref(info)) < 0:
                continue
            mime = _string(info.mime_format)
            if (
                info.type == od.MP4_TRACK_TYPE_METADATA
                and mime
                and "parrot.videometadata" in mime
            ):
                return info
        raise BlackboxError("the recording has no Parrot video metadata track")

    def _start_time(self):
        """Returns when the recording started, in UTC, or None if the MP4 does
        not say."""
        info = od.struct_mp4_media_info()
        if (
            od.mp4_demux_get_media_info(self._demux, ctypes.byref(info)) < 0
            or not info.creation_time
        ):
            return None
        # libmp4 gives the creation time in seconds since the Unix epoch.
        return datetime.fromtimestamp(info.creation_time, timezone.utc)

    def __len__(self):
        return self._track.sample_count

    def frames(self, every=1, raw=False):
        """Yields the metadata of every `every`th frame, with all its decoded
        fields in `raw` if `raw` is set."""
        track = self._track
        buf = (ctypes.c_ubyte * track.sample_max_size)()
        json_buf = ctypes.create_string_buffer(16 << 10)
        index = 0
        while True:
            sample = od.struct_mp4_track_sample()
            res = od.mp4_demux_get_track_sample(
                self._demux, track.id, 1, buf, len(buf), None, 0, ctypes.byref(sample)
            )
            if res < 0:
                raise BlackboxError(f"cannot read sample {index}: error {res}")
            if sample.size == 0:
                return
            if index % every == 0:
                yield self._decode(index, sample, buf, json_buf if raw else None)
            index += 1

    def _decode(self, index, sample, buf, json_buf):
        vbuf = od.struct_vmeta_buffer()
        vbuf.vmeta_buffer_0.cdata = ctypes.cast(buf, type(vbuf.vmeta_buffer_0.cdata))
        vbuf.len = sample.size
        vbuf.pos = 0
        frame = od.POINTER_T(od.struct_vmeta_frame)()
        res = od.vmeta_frame_read2(
            ctypes.byref(vbuf), self._track.mime_format, 0, ctypes.byref(frame)
        )
        video_time = sample.dts / self._track.timescale
        utc_time = None
        if self.start_time is not None:
            utc_time = (self.start_time + timedelta(seconds=video_time)).isoformat(
                timespec="milliseconds"
            )
        if res < 0:
            return FrameMetadata(index, video_time, utc_time)
        try:
            timestamp = ctypes.c_uint64()
            has_timestamp = (
                od.vmeta_frame_get_frame_timestamp(frame, ctypes.byref(timestamp)) == 0
            )
            location = od.struct_vmeta_location()
            has_location = (
                od.vmeta_frame_get_location(frame, ctypes.byref(location)) == 0
                and location.valid
            )
            ground = ctypes.c_double()
            has_ground = (
                od.vmeta_frame_get_ground_distance(frame, ctypes.byref(ground)) == 0
            )
            raw = None
            if (
                json_buf is not None
                and od.vmeta_frame_to_json_str(frame, json_buf, len(json_buf)) >= 0
            ):
                raw = json.loads(json_buf.value)
            return FrameMetadata(
                frame=index,
                video_time=video_time,
                utc_time=utc_time,
                frame_timestamp=timestamp.value if has_timestamp else None,
                latitude=location.latitude if has_location else None,
                longitude=location.longitude if has_location else None,
                altitude_amsl=_finite(location.altitude_egm96amsl)
                if has_location
                else None,
                altitude_wgs84=_finite(location.altitude_wgs84ellipsoid)
                if has_location
                else None,
                ground_distance=_finite(ground.value) if has_ground else None,
                satellites=location.sv_count if has_location else None,
                raw=raw,
            )
        finally:
            od.vmeta_frame_unref(frame)

    def close(self):
        if self._demux:
            od.mp4_demux_close(self._demux)
            self._demux = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# The columns written unless --columns names others. Any field
# libvideo-metadata decodes can be named too, by its path in the frame's raw
# JSON, e.g. speed.north or lfic.target_location.latitude.
COLUMNS = [name for name in FrameMetadata.__dataclass_fields__ if name != "raw"]

# Marks a raw field the frame does not have, e.g. location without a GPS fix.
_MISSING = object()


def needs_raw(columns):
    """Returns whether any of `columns` is a raw field."""
    return any(name not in COLUMNS for name in columns)


def _raw_field(raw, name):
    value = raw
    for key in name.split("."):
        if not isinstance(value, dict) or key not in value:
            return _MISSING
        value = value[key]
    return value


def rows(frames, columns, found=None):
    """Yields each frame as a dict of `columns`, None where the frame lacks
    one. Adds each raw field found in some frame to the set `found`."""
    for frame in frames:
        row = {}
        for name in columns:
            if name in COLUMNS:
                row[name] = getattr(frame, name)
                continue
            value = _raw_field(frame.raw or {}, name)
            if value is _MISSING:
                value = None
            elif found is not None:
                found.add(name)
            row[name] = value
        yield row


def write_csv(rows, columns, out):
    writer = csv.DictWriter(out, columns)
    writer.writeheader()
    for row in rows:
        # A column naming a group of fields, e.g. speed, holds them as JSON.
        writer.writerow(
            {
                k: ""
                if v is None
                else json.dumps(v)
                if isinstance(v, (dict, list))
                else v
                for k, v in row.items()
            }
        )


def write_jsonl(rows, out):
    for row in rows:
        out.write(json.dumps(row) + "\n")


def _flatten(raw, prefix=""):
    for key, value in raw.items():
        if isinstance(value, dict):
            yield from _flatten(value, f"{prefix}{key}.")
        else:
            yield prefix + key


def list_columns(reader, out):
    """Writes the columns the recording has: the default ones, then every raw
    field with the share of frames that have it."""
    counts = {}
    for frame in reader.frames(raw=True):
        for name in _flatten(frame.raw or {}):
            counts[name] = counts.get(name, 0) + 1
    width = max(map(len, COLUMNS + list(counts)))
    for name in COLUMNS:
        out.write(f"{name:{width}}  default\n")
    for name in sorted(counts):
        out.write(
            f"{name:{width}}  {100 * counts[name] / len(reader):5.1f}% of frames\n"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Extract per-frame GPS location and altitude from a video "
        "recorded by a Parrot Anafi."
    )
    parser.add_argument("video", help="the recording, e.g. P5770841.MP4")
    parser.add_argument("-o", "--output", help="where to write (default: stdout)")
    parser.add_argument("-f", "--format", choices=["csv", "jsonl"], default="csv")
    parser.add_argument(
        "-n",
        "--every",
        type=int,
        default=1,
        metavar="N",
        help="keep only every Nth frame (default: every frame)",
    )
    parser.add_argument(
        "-c",
        "--columns",
        metavar="NAMES",
        help="comma-separated columns to write, in order: default "
        "columns or raw fields by dotted name, e.g. "
        "utc_time,latitude,longitude,speed.north "
        "(see --list-columns)",
    )
    parser.add_argument(
        "--list-columns",
        action="store_true",
        help="list the columns the recording has, and exit",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="add every decoded metadata field (jsonl only)",
    )
    args = parser.parse_args(argv)
    if args.every < 1:
        parser.error("--every must be at least 1")
    if args.raw and args.format != "jsonl":
        parser.error("--raw needs --format jsonl")
    if args.raw and args.columns:
        parser.error("--raw and --columns cannot be used together")
    columns = COLUMNS
    if args.columns:
        columns = [name.strip() for name in args.columns.split(",")]
        if not all(columns):
            parser.error("--columns has an empty name")
        if len(set(columns)) != len(columns):
            parser.error("--columns names a column twice")

    found = set()
    try:
        with BlackboxReader(args.video) as reader:
            out = open(args.output, "w", newline="") if args.output else sys.stdout
            try:
                if args.list_columns:
                    list_columns(reader, out)
                    return
                frames = reader.frames(
                    every=args.every, raw=args.raw or needs_raw(columns)
                )
                if args.raw:
                    write_jsonl((_raw_row(frame) for frame in frames), out)
                elif args.format == "csv":
                    write_csv(rows(frames, columns, found), columns, out)
                else:
                    write_jsonl(rows(frames, columns, found), out)
            finally:
                if out is not sys.stdout:
                    out.close()
    except BlackboxError as e:
        sys.exit(f"{args.video}: {e}")
    # A raw field no frame has is likely misspelled; its column is empty.
    unknown = [name for name in columns if name not in COLUMNS and name not in found]
    if unknown:
        sys.exit(f"{args.video}: no frame has {', '.join(unknown)}; see --list-columns")


def _raw_row(frame):
    row = asdict(frame)
    if row["raw"] is None:
        del row["raw"]
    return row


if __name__ == "__main__":
    main()
