"""vtt.py: Zoom's audio transcript into the transcript.json the agent reads.

Zoom writes WebVTT: a WEBVTT header, then cues of the form

    12
    00:01:02.900 --> 00:01:10.430
    Fadel Megahed: what was said

The speaker prefix is kept as a field but is not trusted for anything: the
room microphone attributes every voice to the instructor. Cues are merged into
paragraphs so the model reads prose rather than eight-second slivers, capped
at 30 s so a timestamp copied from the transcript still lands close to the
moment it marks.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_TIME = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})")
_ARROW = re.compile(r"^(\S+)\s+-->\s+(\S+)")
_SPEAKER = re.compile(r"^([^:]{1,60}?):\s+(.*)$")


def _seconds(stamp: str) -> float:
    m = _TIME.match(stamp)
    if not m:
        raise ValueError(f"bad VTT time {stamp!r}")
    h, mi, s, ms = (int(g) for g in m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000


def parse_vtt(text: str) -> list[dict]:
    cues: list[dict] = []
    block: list[str] = []
    for raw in text.splitlines() + [""]:
        line = raw.strip()
        if line:
            block.append(line)
            continue
        if block:
            cue = _parse_block(block)
            if cue:
                cues.append(cue)
            block = []
    return cues


def _parse_block(lines: list[str]) -> dict | None:
    if lines[0].upper().startswith("WEBVTT"):
        return None
    times = next((i for i, l in enumerate(lines) if "-->" in l), None)
    if times is None:
        return None
    m = _ARROW.match(lines[times])
    if not m:
        return None
    text = " ".join(lines[times + 1:]).strip()
    speaker = ""
    sm = _SPEAKER.match(text)
    if sm:
        speaker, text = sm.group(1).strip(), sm.group(2).strip()
    return {"start": _seconds(m.group(1)), "end": _seconds(m.group(2)),
            "speaker": speaker, "text": text}


def merge_cues(cues: list[dict], gap: float = 1.5,
               max_len: float = 30.0) -> list[dict]:
    merged: list[dict] = []
    for c in cues:
        if merged:
            last = merged[-1]
            same = c["speaker"] == last["speaker"]
            close = c["start"] - last["end"] <= gap
            short = c["end"] - last["start"] <= max_len
            if same and close and short:
                last["end"] = c["end"]
                last["text"] = f"{last['text']} {c['text']}".strip()
                continue
        merged.append(dict(c))
    return merged


def write_transcript(vtt_path: Path, out_path: Path) -> int:
    cues = parse_vtt(Path(vtt_path).read_text(encoding="utf-8"))
    segments = merge_cues(cues)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "segments": segments,
        "metadata": {"source": Path(vtt_path).name, "cues": len(cues)},
    }, indent=1), encoding="utf-8")
    return len(segments)
