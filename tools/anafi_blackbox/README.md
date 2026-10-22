# anafi-blackbox

Extracts per-frame metadata (GPS location, altitude, UTC time) from videos a
Parrot Anafi recorded to its SD card. The drone stores the same metadata it
streams ([video metadata](https://developer.parrot.com/docs/pdraw/video-metadata.html))
in a track beside the video; this reads it with olympe's libmp4 and
libvideo-metadata, without decoding any frames, so a long recording takes a
few seconds.

```
uv run parrot-anafi-blackbox P5770841.MP4 -o flight.csv
uv run parrot-anafi-blackbox P5770841.MP4 -f jsonl -n 30   # one frame in 30
uv run parrot-anafi-blackbox P5770841.MP4 -f jsonl --raw   # every decoded field
```

Default columns: `frame, video_time, utc_time, frame_timestamp, latitude,
longitude, altitude_amsl, altitude_wgs84, ground_distance, satellites`.
Location fields are empty while the drone has no GPS fix. `utc_time` is the
recording's start, which the MP4 stores only to the second, plus `video_time`.

`--columns` picks the columns, in order. Besides the default ones, it takes any
field libvideo-metadata decodes, by its dotted path in `--raw`'s JSON;
`--list-columns` lists them all, with the share of frames that have each:

```
uv run parrot-anafi-blackbox P5770841.MP4 --list-columns
uv run parrot-anafi-blackbox P5770841.MP4 \
    -c utc_time,latitude,longitude,speed.north,battery_percentage,lfic.target_location.latitude
```

A frame without a field leaves its column empty. If no frame has it, the name
is likely misspelled, and the tool exits with an error after writing.

Runs on x86-64 Linux only, the one platform parrot-olympe is published for.

Tests read a real recording from `ANAFI_RECORDING` (default
`~/Videos/P5770841.MP4`) and are skipped without one:

```
uv run pytest
```
