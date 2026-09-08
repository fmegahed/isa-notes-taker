"""The orchestration that does not need a model: finding the Zoom files,
remembering flags in state.json, building the header, and refusing to run
on a folder that is not one class."""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import session as S   # noqa: E402

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    sd = d / "sessions" / "class03"
    sd.mkdir(parents=True)
    try:
        S.find_media(sd)
        assert False, "should refuse with no mp4"
    except SystemExit as e:
        assert "mp4" in str(e)
    (sd / "GMT20260831-123000_Recording_2426x1516.mp4").write_bytes(b"")
    (sd / "GMT20260831-123000_Recording.transcript.vtt").write_text("WEBVTT\n")
    (sd / "GMT20260831-123000_Recording.m4a").write_bytes(b"")
    mp4, vtt = S.find_media(sd)
    assert mp4.suffix == ".mp4" and vtt.suffix == ".vtt"
    (sd / "second.mp4").write_bytes(b"")
    try:
        S.find_media(sd)
        assert False, "two videos must be refused"
    except SystemExit as e:
        assert "exactly one" in str(e)
    (sd / "second.mp4").unlink()
    print("media found by extension, exactly one of each")

    out = sd / "out"
    assert S.load_state(out) == {}
    S.save_state(out, {"instructor": "Fadel Megahed"})
    assert S.load_state(out)["instructor"] == "Fadel Megahed"
    print("state round-trips")

    deck_dir = d / "isa401" / "lectures" / "03_r_foundations"
    deck_dir.mkdir(parents=True)
    deck = deck_dir / "03_r_foundations.Rmd"
    deck.write_text('---\ntitle: "ISA 401"\nsubtitle: "03: Foundations"\n---\n')
    (d / "class_code" / "markdowns").mkdir(parents=True)
    rmd = d / "class_code" / "markdowns" / "03_r_basics.Rmd"
    rmd.write_text("x")
    args = S.parse_args(["sessions/class03", "--instructor", "Fadel Megahed",
                         "--video-url", "https://z/rec"])
    src = S.resolve_sources(sd, args, {}, project_root=d)
    assert src["deck"] == deck and src["class_rmd"] == rmd
    assert src["date"] == "2026-08-31" and src["video_url"] == "https://z/rec"
    # Saved flags come back without being passed again.
    S.save_state(out, {k: (str(v) if isinstance(v, Path) else v)
                       for k, v in src.items()})
    again = S.resolve_sources(sd, S.parse_args(["sessions/class03"]),
                              S.load_state(out), project_root=d)
    assert again["instructor"] == "Fadel Megahed" and again["deck"] == deck
    header = S.header_for(src)
    assert header.startswith("---\ntitle: \"ISA 401\"")
    assert "subtitle: \"03: Foundations\"" in header
    assert "[Recording](https://z/rec)" in header
    assert "github.com/fmegahed/isa401a/blob/main/markdowns/03_r_basics.Rmd" in header
    assert "fmegahed.github.io/isa401/fall2026/class03/03_r_foundations.html" in header
    print("sources resolved from folder name, flags, and saved state; header built")
