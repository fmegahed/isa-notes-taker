"""Scene stills come from ffmpeg's scene-change score, plus the first frame,
which scene detection never emits. A synthetic video of three flat colours
with hard cuts at 2 s and 4 s must give exactly three stills with those
intervals, and a threshold of 0 must trip the runaway guard rather than
write a still per frame."""
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
    assert json.loads((out / "scenes.json").read_text())[0]["id"] == 1
    assert scenes.load(out) == found
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
