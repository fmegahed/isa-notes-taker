"""scenes.py: what was on the shared screen, as one still per scene change.

A Zoom transcript is what was said. Everything the instructor showed, in
RStudio, a rendered page, or a GUI tool, is lost unless it is pulled from the
video. ffmpeg's scene score does that without any model: a still is written
each time the frame changes materially, and the first frame is always kept
because scene detection never emits it.

Each still's interval runs from its own time to the next still's. The marks
are spliced into the transcript so the model sees a screen change at the
place it is reading, and an index lists every still with its interval and
path so the model can open the ones that matter.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from media import format_timestamp

_PTS = re.compile(r"Parsed_showinfo\S*.*?pts_time:\s*([0-9.]+)")


def _duration(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(video)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def _first_frame(video: Path, dest: Path) -> bool:
    return subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vframes", "1",
         "-vf", "scale=960:-2", "-q:v", "3", str(dest)],
        capture_output=True).returncode == 0


def _cuts(video: Path, tmp_dir: Path, threshold: float) -> list[tuple[float, Path]]:
    """Run scene detection once. Returns (time, jpeg) per detected change."""
    pattern = tmp_dir / "cut-%06d.jpg"
    vf = f"scale=960:-2,select=gt(scene\\,{threshold:.3f}),showinfo"
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "info", "-i", str(video), "-vf", vf,
         "-fps_mode", "vfr", "-q:v", "3", str(pattern)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    times = [float(m.group(1)) for m in _PTS.finditer(proc.stderr)]
    files = sorted(tmp_dir.glob("cut-*.jpg"),
                    key=lambda p: int(p.stem.split("-")[1]))
    if len(times) != len(files):
        print(f"  scene detection: {len(times)} timestamp(s) but "
              f"{len(files)} still(s) parsed from ffmpeg's output; "
              f"truncating to the shorter", flush=True)
    return list(zip(times, files))


def _sample_evenly(cuts: list[tuple[float, Path]],
                    n_keep: int) -> list[tuple[float, Path]]:
    """Evenly spaced subsample of `cuts`, spanning the whole list, so a scan
    that never converges under the guard still has stills past its
    midpoint instead of only ones from the start."""
    if n_keep <= 0:
        return []
    if len(cuts) <= n_keep:
        return cuts
    if n_keep == 1:
        return [cuts[0]]
    idxs = sorted({round(i * (len(cuts) - 1) / (n_keep - 1))
                   for i in range(n_keep)})
    return [cuts[i] for i in idxs]


def detect(video: Path, out_dir: Path, threshold: float = 0.30,
           max_scenes: int = 400) -> list[dict]:
    video = Path(video).resolve()
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    tmp = out_dir / "_tmp"
    tmp.mkdir()

    try:
        t = threshold
        for attempt in range(4):
            for f in tmp.glob("*.jpg"):
                f.unlink()
            cuts = _cuts(video, tmp, t)
            if len(cuts) + 1 <= max_scenes or attempt == 3:
                break
            print(f"  scene detection at {t:.2f} gave {len(cuts)} changes; "
                  f"raising the threshold", flush=True)
            t = t * 1.5 if t > 0 else 0.3

        if len(cuts) > max_scenes - 1:
            cuts = _sample_evenly(cuts, max_scenes - 1)
            print(f"  scene detection stayed above {max_scenes} after 4 "
                  f"attempts; keeping an even sample of "
                  f"{max_scenes - 1} changes", flush=True)

        duration = _duration(video)
        starts: list[tuple[float, Path]] = []
        first = out_dir / "scene-001.jpg"
        if not _first_frame(video, first):
            raise SystemExit(
                f"could not extract the first frame of {video}; is the "
                f"file a readable video?")
        starts.append((0.0, first))
        for n, (at, src) in enumerate(cuts, start=len(starts) + 1):
            dest = out_dir / f"scene-{n:03d}.jpg"
            shutil.move(str(src), dest)
            starts.append((at, dest))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    result = []
    for i, (at, path) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else duration
        result.append({"id": i + 1, "path": str(path.resolve()),
                       "start": round(at, 3), "end": round(end, 3)})
    (out_dir / "scenes.json").write_text(
        json.dumps({"threshold": t, "scenes": result}, indent=1))
    return result


def load(out_dir: Path) -> list[dict]:
    f = Path(out_dir) / "scenes.json"
    if not f.exists():
        return []
    data = json.loads(f.read_text())
    return data["scenes"] if isinstance(data, dict) else data


def load_threshold(out_dir: Path) -> float | None:
    f = Path(out_dir) / "scenes.json"
    if not f.exists():
        return None
    data = json.loads(f.read_text())
    return data.get("threshold") if isinstance(data, dict) else None


def marks(scenes: list[dict]) -> list[tuple[float, str]]:
    return [(s["start"], f"[{format_timestamp(s['start'])}] "
                         f"=== scene {s['id']} up: {s['path']} ===")
            for s in scenes]


def index_text(scenes: list[dict]) -> str:
    if not scenes:
        return ""
    rows = [f"  Scene {s['id']:>3}: {format_timestamp(s['start'])} to "
            f"{format_timestamp(s['end'])}\n    {s['path']}" for s in scenes]
    return (
        f"**Screen stills** ({len(scenes)}): one JPEG per change of what was "
        f"on the shared screen, with the interval it was up. Open a still "
        f"with your Read tool when the transcript refers to something shown "
        f"(code, output, a chart, a menu) and when a scene marker appears in "
        f"the transcript where code or a GUI is being used. You do not need "
        f"to open every still; you do need to open the ones that carry "
        f"content the transcript does not.\n\n" + "\n".join(rows) + "\n")
