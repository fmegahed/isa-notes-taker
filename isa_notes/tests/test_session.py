"""The orchestration that does not need a model: finding the Zoom files,
remembering flags in state.json, building the header, and refusing to run
on a folder that is not one class."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import qmd            # noqa: E402
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
    assert src["instructor_pronouns"] is None
    pronoun_args = S.parse_args(["sessions/class03", "--instructor-pronouns", "he/him"])
    assert pronoun_args.instructor_pronouns == "he/him"
    pronoun_src = S.resolve_sources(sd, pronoun_args, {}, project_root=d)
    assert pronoun_src["instructor_pronouns"] == "he/him"
    S.save_state(out, {k: (str(v) if isinstance(v, Path) else v)
                       for k, v in pronoun_src.items()})
    reloaded = S.load_state(out)
    assert reloaded["instructor_pronouns"] == "he/him"
    again_pronoun = S.resolve_sources(sd, S.parse_args(["sessions/class03"]),
                                      reloaded, project_root=d)
    assert again_pronoun["instructor_pronouns"] == "he/him"
    print("instructor pronouns flag resolves and survives a state round trip")
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
    assert "on Canvas" not in header, "a linked recording needs no Canvas note"
    # Without a URL the page says where the recording lives instead of linking it.
    no_url = S.header_for({**src, "video_url": None})
    assert "[Recording]" not in no_url and "The recording is on Canvas." in no_url
    assert "github.com/fmegahed/isa401a/blob/main/markdowns/03_r_basics.Rmd" in header
    assert "fmegahed.github.io/isa401/fall2026/class03/03_r_foundations.html" in header
    print("sources resolved from folder name, flags, and saved state; header built")

    # A deck path saved in state that no longer exists on disk must not
    # crash resolve_sources; it heals by searching for the real deck again.
    stale_state = {"deck": str(deck_dir / "gone.Rmd")}
    healed = S.resolve_sources(sd, S.parse_args(["sessions/class03"]),
                               stale_state, project_root=d)
    assert healed["deck"] == deck
    print("stale deck path in state heals via find_deck")

    # A path given on THIS invocation via --class-rmd (or --deck) is not
    # healed if it is wrong; it is a misconfiguration and stops the run.
    bad_args = S.parse_args(["sessions/class03", "--class-rmd",
                             str(deck_dir / "nope.Rmd")])
    try:
        S.resolve_sources(sd, bad_args, {}, project_root=d)
        assert False, "a nonexistent --class-rmd must raise SystemExit"
    except SystemExit as e:
        assert "--class-rmd" in str(e) and "nope.Rmd" in str(e)
    print("a flag-supplied class RMD that does not exist raises SystemExit")

    # deck_meta_for falls back to a generic title when the deck is missing.
    meta = S.deck_meta_for({"deck": Path("nope.Rmd"), "n": 3})
    assert meta["title"] == "ISA 401 Class 03" and meta["subtitle"] == ""
    print("deck_meta_for falls back when the deck path does not exist")

    # stage_verify refuses to run without notes.qmd, before touching the
    # backend (no notes.qmd exists under this fresh out dir).
    out3 = d / "sessions" / "class03_verify_only" / "out"
    try:
        S.stage_verify(out3, mp4, out3 / "transcript.json", [], src, args)
        assert False, "stage_verify must refuse without notes.qmd"
    except SystemExit as e:
        assert "write them first" in str(e)
    print("stage_verify refuses to run without notes.qmd")

    # _ctx passes a state_file so questions asked mid-run survive a crash.
    tj_ctx = out3 / "transcript.json"
    tj_ctx.parent.mkdir(parents=True, exist_ok=True)
    tj_ctx.write_text(json.dumps({"segments": []}), encoding="utf-8")
    ctx = S._ctx(out3, mp4, tj_ctx, [])
    assert ctx.state_file == out3 / "agent_state.json"
    print("_ctx persists questions to agent_state.json")

    # Pre-flight check for the external tools the pipeline shells out to.
    try:
        S.require_tools(["definitely-not-a-real-binary-xyz"])
        assert False, "require_tools must refuse a missing binary"
    except SystemExit as e:
        assert "definitely-not-a-real-binary-xyz" in str(e)
    S.require_tools(["python"])  # must not raise
    print("require_tools checks the PATH before anything else runs")

    # --regen (notes.qmd already present) archives the old questions file
    # instead of leaving it to describe questions about a document that no
    # longer exists.
    out4 = d / "sessions" / "class03_regen" / "out"
    out4.mkdir(parents=True)
    notes4 = out4 / "notes.qmd"
    notes4.write_text("# old notes\n", encoding="utf-8")
    qfile4 = out4 / "notes.qmd.questions.json"
    qfile4.write_text('{"questions": []}', encoding="utf-8")
    tj4 = out4 / "transcript.json"
    tj4.write_text(json.dumps({"segments": []}), encoding="utf-8")

    def fake_run_agent(*, output_file, **kwargs):
        output_file.write_text("# new notes\n", encoding="utf-8")
        return "# new notes\n"

    real_run_agent = S.run_agent
    S.run_agent = fake_run_agent
    try:
        regen_args = S.parse_args(["sessions/class03"])
        S.stage_write(out4, mp4, tj4, [], src, regen_args)
    finally:
        S.run_agent = real_run_agent
    assert not qfile4.exists()
    assert (out4 / "notes.qmd.questions.json.bak").read_text(encoding="utf-8") \
        == '{"questions": []}'
    print("--regen archives the old questions file to a .bak")

    # stage_scenes re-detects when scenes.json was made at a different
    # threshold than the one now requested, instead of serving stale stills.
    out5 = d / "sessions" / "class03_scenes" / "out"
    sdir5 = out5 / "scenes"
    sdir5.mkdir(parents=True)
    (sdir5 / "scenes.json").write_text(json.dumps({
        "threshold": 0.30, "scenes": [{"id": 1, "path": "x.jpg",
                                       "start": 0.0, "end": 1.0}]}),
        encoding="utf-8")

    calls = []

    def fake_detect(mp4_arg, out_dir, threshold=0.30, **kwargs):
        calls.append(threshold)
        return [{"id": 1, "path": "new.jpg", "start": 0.0, "end": 1.0}]

    real_detect = S.SC.detect
    S.SC.detect = fake_detect
    try:
        same = S.stage_scenes(mp4, out5, True, 0.30)
        assert calls == [], "matching threshold must serve the cache"
        assert same[0]["path"] == "x.jpg"
        different = S.stage_scenes(mp4, out5, True, 0.55)
        assert calls == [0.55], "differing threshold must re-detect"
        assert different[0]["path"] == "new.jpg"
    finally:
        S.SC.detect = real_detect
    print("stage_scenes re-detects when the cached threshold no longer matches")

    # stage_render refuses to hand quarto a file with an executable fence,
    # and repairs a front matter block the model altered, before rendering.
    out6 = d / "sessions" / "class03_render" / "out"
    out6.mkdir(parents=True)
    header6 = S.header_for(src)
    render_args = S.parse_args(["sessions/class03"])
    notes6 = out6 / "notes.qmd"

    notes6.write_text(header6 + "\n## Body\n\n```{r}\n1 + 1\n```\n",
                      encoding="utf-8")
    try:
        S.stage_render(out6, mp4, out6 / "transcript.json", [], src, render_args)
        assert False, "an executable fence must refuse to render"
    except SystemExit as e:
        assert "```{r}" in str(e), e
    print("stage_render refuses an executable code fence before rendering")

    altered6 = header6.replace("engine: markdown", "engine: knitr")
    notes6.write_text(altered6 + "\n## Body\n\nSome prose.\n", encoding="utf-8")
    ok6 = S.stage_render(out6, mp4, out6 / "transcript.json", [], src, render_args)
    assert ok6, "restored front matter should render cleanly"
    assert qmd.front_matter_matches(notes6, header6)
    print("stage_render restores an altered front matter block before rendering")

    # "write them first" messages, and --publish's own guard, mention a
    # notes.qmd.bak from an interrupted run when one is present.
    out7 = d / "sessions" / "class03_bak" / "out"
    out7.mkdir(parents=True)
    try:
        S.stage_verify(out7, mp4, out7 / "transcript.json", [], src, render_args)
        assert False
    except SystemExit as e:
        assert "write them first" in str(e) and ".bak" not in str(e)
    try:
        S.stage_publish(out7 / "notes.qmd", str(d / "site"))
        assert False, "stage_publish must refuse without notes.qmd"
    except SystemExit as e:
        assert "write them first" in str(e)
    (out7 / "notes.qmd.bak").write_text("old", encoding="utf-8")
    try:
        S.stage_answer(out7, mp4, out7 / "transcript.json", [], src, render_args)
        assert False
    except SystemExit as e:
        assert "notes.qmd.bak" in str(e) and "interrupted run" in str(e)
    print("no-notes messages name a notes.qmd.bak from an interrupted run")

# Importing session.py must not crash a run just because stdout cannot
# encode a character the model wrote, such as an emoji, in cp1252. Strip
# PYTHONIOENCODING/PYTHONUTF8 from the child's env so a UTF-8 default set
# on this machine cannot mask the console's real (cp1252) encoding.
code = (
    "import sys; sys.path.insert(0, r'" + str(HERE) + "'); "
    "import session; print('\\U0001f3c6')"
)
env = os.environ.copy()
env.pop("PYTHONIOENCODING", None)
env.pop("PYTHONUTF8", None)
result = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env)
assert result.returncode == 0, result.stderr
print("console encoding cannot kill a run")
