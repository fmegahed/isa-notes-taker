"""Scene stills come from ffmpeg's scene-change score, plus the first frame,
which scene detection never emits. A synthetic video of three flat colours
with hard cuts at 2 s and 4 s must give exactly three stills with those
intervals, and a threshold of 0 must trip the runaway guard rather than
write a still per frame."""
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import scenes   # noqa: E402
from media import format_transcript   # noqa: E402

assert shutil.which("ffmpeg"), "ffmpeg is required"

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    video = d / "cuts.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=red:s=320x240:d=2:r=10",
        "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=2:r=10",
        "-f", "lavfi", "-i", "color=c=green:s=320x240:d=2:r=10",
        "-filter_complex", "[0][1][2]concat=n=3:v=1:a=0",
        "-pix_fmt", "yuv420p", str(video)], check=True)

    out = d / "scenes"
    found = scenes.detect(video, out, threshold=0.3)
    assert [s["id"] for s in found] == [1, 2, 3], found
    assert found[0]["start"] == 0.0
    assert abs(found[1]["start"] - 2.0) < 0.2 and abs(found[2]["start"] - 4.0) < 0.2
    assert abs(found[0]["end"] - found[1]["start"]) < 1e-6
    assert abs(found[2]["end"] - 6.0) < 0.3, found[2]
    for s in found:
        assert Path(s["path"]).is_file() and Path(s["path"]).is_absolute()
    raw = json.loads((out / "scenes.json").read_text())
    assert raw["threshold"] == 0.3 and raw["scenes"][0]["id"] == 1, raw
    assert scenes.load(out) == found
    assert scenes.load_threshold(out) == 0.3
    print("three stills: first frame plus two cuts, with intervals")

    # A threshold of 0 marks every frame; the guard raises the threshold
    # instead of writing 60 stills.
    shutil.rmtree(out)
    guarded = scenes.detect(video, out, threshold=0.0, max_scenes=5)
    assert len(guarded) <= 5, len(guarded)
    print("runaway guard holds the count down")

    segs = [{"start": 0.5, "end": 1.9, "text": "red"},
            {"start": 2.5, "end": 3.9, "text": "blue"},
            {"start": 4.5, "end": 5.9, "text": "green"}]
    text = format_transcript(segs, scenes.marks(found))
    lines = text.splitlines()
    assert lines[0].startswith("[00:00:00] === scene 1 up:"), lines[0]
    assert lines[1] == "[00:00:00] red" or lines[1] == "[00:00:01] red", lines[1]
    assert "=== scene 2 up:" in lines[2], lines
    assert "=== scene 3 up:" in lines[4], lines
    idx = scenes.index_text(found)
    assert "Scene   1: 00:00:00 to 00:00:02" in idx, idx
    assert found[0]["path"] in idx
    print("marks splice into the transcript; index lists intervals and paths")

    # Truncation must sample evenly across the whole scan, not keep only
    # the earliest cuts. cuts.mp4 above yields only 2 raw cuts at threshold
    # 0 (flat colours score 0 between identical frames), and a gradient
    # testsrc video's per-frame changes score below 0.3, so both converge
    # under the guard's threshold escalation before truncation is ever
    # reached. A video with a hard colour cut every second keeps 5 raw cuts
    # that all score near 1.0, which survives escalation through 3
    # attempts and forces the truncation path on the 4th.
    flicker = d / "flicker.mp4"
    colors = ["red", "blue", "green", "yellow", "magenta", "cyan"]
    inputs = []
    for c in colors:
        inputs += ["-f", "lavfi", "-i", f"color=c={c}:s=320x240:d=1:r=10"]
    n = len(colors)
    filt = "".join(f"[{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0"
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs,
                     "-filter_complex", filt, "-pix_fmt", "yuv420p",
                     str(flicker)], check=True)
    sampled = scenes.detect(flicker, d / "sampled", threshold=0.0, max_scenes=3)
    assert len(sampled) == 3, sampled
    starts = [s["start"] for s in sampled]
    assert starts == sorted(starts) and len(set(starts)) == 3, starts
    assert abs(sampled[-1]["end"] - 6.0) < 0.3, sampled[-1]
    print("even sample spans the whole scan instead of just the start")

    # ffmpeg's showinfo timestamps and the written stills can disagree in
    # count (a dropped frame, say); _cuts must warn and truncate to the
    # shorter rather than let zip silently drop the mismatch unremarked.
    class _FakeProc:
        def __init__(self, stderr):
            self.stderr = stderr

    tmp_dir = d / "tmp_cuts"
    tmp_dir.mkdir()
    (tmp_dir / "cut-000001.jpg").write_bytes(b"x")
    (tmp_dir / "cut-000002.jpg").write_bytes(b"x")
    real_run = scenes.subprocess.run
    scenes.subprocess.run = lambda *a, **k: _FakeProc(
        "Parsed_showinfo pts_time:1.0\n"
        "Parsed_showinfo pts_time:2.0\n"
        "Parsed_showinfo pts_time:3.0\n")
    real_stdout, sys.stdout = sys.stdout, io.StringIO()
    try:
        mismatched = scenes._cuts(Path("fake.mp4"), tmp_dir, 0.3)
        printed = sys.stdout.getvalue()
    finally:
        sys.stdout = real_stdout
        scenes.subprocess.run = real_run
    assert len(mismatched) == 2, mismatched
    assert "3" in printed and "2" in printed, printed
    print("_cuts warns and truncates on a timestamp/still count mismatch")
