#!/usr/bin/env python3
"""session.py: one recorded ISA 401 class into one page of companion notes.

    python isa_notes/session.py sessions/class03 [--class-rmd F] [--deck F]
        [--instructor NAME] [--video-url URL] [--video-url-template T]
        [--answer] [--verify] [--no-verify] [--regen]
        [--publish] [--pdf] [--deploy DIR]
        [--no-scenes] [--scene-threshold X] [--wait]
        [--backend B] [--model M] [--frame-model M]

The session folder holds Zoom's download (one .mp4, one .vtt). Everything
the tool writes goes to <session>/out/. Stages are cached by the presence
of their output: transcript.json, scenes/, notes.qmd. --regen rewrites the
notes; --answer and --verify run those passes alone.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Windows consoles default to cp1252, and the backend prints model text
# verbatim; a stray character (an emoji, say) must not kill a run.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import instructions as I                                   # noqa: E402
import qmd                                                 # noqa: E402
import scenes as SC                                        # noqa: E402
import vtt                                                 # noqa: E402
from claude_backend import (BACKENDS, collect_followup_answers,   # noqa: E402
                            count_todos, mark_answers_applied,
                            questions_file_for, run_agent)
from media import format_transcript                        # noqa: E402
from notes_tools import NotesToolContext                   # noqa: E402

PROJECT_ROOT = HERE.parent
NOTES_SITE = PROJECT_ROOT / "notes_site"
DOCS_DIR = PROJECT_ROOT / "docs"
SLIDES_URL = "https://fmegahed.github.io/isa401/fall2026/class{n:02d}/{stem}.html"
CLASS_CODE_URL = "https://github.com/fmegahed/isa401a/blob/main/markdowns/{name}"
TS_NOTE = ("Timestamps before each paragraph are hh:mm:ss into the "
           "recording; drag the player there to hear the passage.")
# The recording itself is not linked from the page unless --video-url is
# given; students find it on Canvas.
RECORDING_NOTE = "The recording is on Canvas."
SAVED_KEYS = ("instructor", "instructor_pronouns", "video_url",
              "video_url_template", "deck", "class_rmd", "date")


# -- inputs ------------------------------------------------------------------

def require_tools(names: list[str]) -> None:
    missing = [n for n in names if shutil.which(n) is None]
    if missing:
        raise SystemExit("missing on PATH: " + ", ".join(missing)
                         + "; install them before running")


def find_media(session_dir: Path) -> tuple[Path, Path]:
    session_dir = Path(session_dir)
    mp4 = sorted(session_dir.glob("*.mp4"))
    vtts = sorted(session_dir.glob("*.vtt"))
    if len(mp4) != 1:
        raise SystemExit(f"{session_dir}: need exactly one .mp4, found {len(mp4)}")
    if len(vtts) != 1:
        raise SystemExit(f"{session_dir}: need exactly one .vtt, found {len(vtts)}")
    return mp4[0], vtts[0]


def load_state(out: Path) -> dict:
    f = Path(out) / "state.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def save_state(out: Path, state: dict) -> None:
    Path(out).mkdir(parents=True, exist_ok=True)
    (Path(out) / "state.json").write_text(json.dumps(state, indent=2),
                                          encoding="utf-8")


def _resolve_path(flag_value, state_value, flag_name: str) -> Path | None:
    """A path supplied on this invocation must exist, or the run is
    misconfigured and should stop now rather than silently search for a
    substitute. A path recovered from a previous run's state.json may be
    stale (the file was moved or renamed since); the caller heals that case
    by searching for the real file, so return None for it to try."""
    if flag_value not in (None, ""):
        p = Path(flag_value)
        if not p.exists():
            raise SystemExit(f"--{flag_name} {p} does not exist")
        return p
    if state_value:
        p = Path(state_value)
        return p if p.exists() else None
    return None


def resolve_sources(session_dir: Path, args, state: dict,
                    project_root: Path = PROJECT_ROOT) -> dict:
    n = qmd.class_number(session_dir)
    mp4, _ = find_media(session_dir) if list(Path(session_dir).glob("*.mp4")) \
        else (None, None)

    def pick(flag, key):
        return flag if flag not in (None, "") else state.get(key)

    deck = _resolve_path(args.deck, state.get("deck"), "deck")
    if deck is None:
        deck = qmd.find_deck(n, project_root / "isa401")
    rmd = _resolve_path(args.class_rmd, state.get("class_rmd"), "class-rmd")
    if rmd is None:
        rmd = qmd.find_class_rmd(n, project_root / "class_code")
    date = state.get("date") or (qmd.zoom_date(mp4.name) if mp4 else None)
    return {
        "instructor": pick(args.instructor, "instructor") or "Fadel Megahed",
        "instructor_pronouns": pick(args.instructor_pronouns, "instructor_pronouns")
        or I.DEFAULT_PRONOUNS,
        "video_url": pick(args.video_url, "video_url"),
        "video_url_template": pick(args.video_url_template, "video_url_template"),
        "deck": deck, "class_rmd": rmd, "date": date, "n": n,
    }


def deck_meta_for(src: dict) -> dict:
    deck = src.get("deck")
    if deck and Path(deck).exists():
        return qmd.deck_meta(deck)
    return {"title": f"ISA 401 Class {src['n']:02d}", "subtitle": ""}


def header_for(src: dict, description: str | None = None,
               extra_links: dict[str, str] | None = None,
               css: str | None = "ts.css") -> str:
    """The page title is the deck's subtitle (the class-specific part,
    e.g. "03: Foundations"), else "Class NN"; the subtitle is the deck's
    title (the course name), else "ISA 401" -- swapped from the deck's own
    layout so a listing of pages shows the class, not the course, on
    every row. `description` is left to the caller (stage_write has none
    yet; stage_publish fills it from the page body). `css` defaults to
    "ts.css" for the per-session page; stage_publish passes css=None for
    the site copy, since notes_site/'s own scss already carries the same
    .ts rules and no ts.css file sits beside the published page."""
    deck = src.get("deck")
    meta = deck_meta_for(src)
    title = meta["subtitle"] or f"Class {src['n']:02d}"
    subtitle = meta["title"] or "ISA 401"
    links = {
        "Slides": SLIDES_URL.format(n=src["n"], stem=Path(deck).stem) if deck else None,
        "Class code": CLASS_CODE_URL.format(name=Path(src["class_rmd"]).name)
        if src.get("class_rmd") else None,
        "Recording": src.get("video_url"),
    }
    if extra_links:
        links.update(extra_links)
    note = TS_NOTE if src.get("video_url") else f"{RECORDING_NOTE} {TS_NOTE}"
    return qmd.front_matter(title, subtitle, src.get("date"), links, note,
                            description=description, css=css)


# -- stages ------------------------------------------------------------------

def stage_transcript(vtt_path: Path, out: Path) -> Path:
    tj = out / "transcript.json"
    if tj.exists():
        print(f"  transcript.json exists ({tj})")
    else:
        n = vtt.write_transcript(vtt_path, tj)
        print(f"  transcript.json: {n} segments")
    return tj


def stage_scenes(mp4: Path, out: Path, enabled: bool, threshold: float) -> list[dict]:
    sdir = out / "scenes"
    if not enabled:
        return []
    if (sdir / "scenes.json").exists():
        cached_threshold = SC.load_threshold(sdir)
        if cached_threshold is not None and abs(cached_threshold - threshold) > 1e-9:
            print(f"  scenes.json was made at threshold {cached_threshold}, "
                 f"not the requested {threshold}; the cached stills are "
                 f"stale, re-detecting")
        else:
            found = SC.load(sdir)
            print(f"  scenes: {len(found)} stills exist")
            return found
    print("  detecting scene changes (a few minutes for an 80 minute class)")
    found = SC.detect(mp4, sdir, threshold=threshold)
    print(f"  scenes: {len(found)} stills")
    return found


def _segments(tj: Path) -> list[dict]:
    return json.loads(tj.read_text(encoding="utf-8"))["segments"]


def _ctx(out: Path, mp4: Path, tj: Path, found: list[dict]) -> NotesToolContext:
    segs = _segments(tj)
    return NotesToolContext(
        refs_dir=out / "refs", video_path=mp4,
        total_duration=segs[-1]["end"] if segs else 0.0,
        transcript_path=tj, boards=found,
        diagrams_dir=(out / "crops") if found else None,
        state_file=out / "agent_state.json")


def _transcript_text(tj: Path, found: list[dict]) -> str:
    return format_transcript(_segments(tj), SC.marks(found))


def stage_write(out: Path, mp4: Path, tj: Path, found: list[dict], src: dict,
                args) -> Path:
    notes = out / "notes.qmd"
    (out / "ts.css").write_bytes((HERE / "ts.css").read_bytes())
    header = header_for(src)
    meta = deck_meta_for(src)
    title = meta.get("subtitle") or f"Class {src['n']:02d}"
    user = I.write_message(
        title=title, date=src.get("date"), instructor=src["instructor"],
        deck=src.get("deck"), class_rmd=src.get("class_rmd"),
        transcript_text=_transcript_text(tj, found),
        scene_index=SC.index_text(found), header=header,
        pronouns=src.get("instructor_pronouns"))
    if notes.exists():
        # --regen starts a fresh write; old open questions no longer apply
        # to whatever the agent writes this time, but are kept as a .bak
        # rather than deleted outright.
        qfile = questions_file_for(notes)
        if qfile.exists():
            bak = qfile.with_name(qfile.name + ".bak")
            bak.unlink(missing_ok=True)
            qfile.replace(bak)
    print(f"  writing notes with the {args.backend} backend")
    run_agent(system_prompt=I.SYSTEM_PROMPT, user_text=user,
              ctx=_ctx(out, mp4, tj, found), output_file=notes,
              backend=args.backend, model=args.model,
              frame_model=args.frame_model, wait_for_answers=args.wait,
              role="write", log_dir=out / "logs")
    if qmd.ensure_front_matter(notes, header):
        print("  (front matter was missing; prepended)")
    return notes


def _no_notes_message(notes: Path) -> str:
    msg = f"No notes at {notes}; write them first."
    bak = notes.with_name(notes.name + ".bak")
    if bak.exists():
        msg += f" (a {bak.name} from an interrupted run is present)"
    return msg


def _rebuild_docs() -> None:
    """docs/ is what GitHub Pages serves; it is rebuilt from scratch from
    the just-rendered notes_site/_site every publish (not merged with
    whatever a project render there happens to leave behind), so a class
    folder removed from notes_site/ actually disappears from docs/ too,
    and a stale file from an earlier render or a manual edit cannot
    linger."""
    site_dir = NOTES_SITE / "_site"
    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    shutil.copytree(site_dir, DOCS_DIR)
    (DOCS_DIR / ".nojekyll").write_bytes(b"")


def stage_publish(out: Path, src: dict, args) -> Path:
    """Land one class's notes.qmd as a page of the notes_site/ project,
    then render the whole site (its listing needs every class's page, not
    just this one) and rebuild docs/ from that render. Returns the
    class's target folder."""
    notes = out / "notes.qmd"
    if not notes.exists():
        raise SystemExit(_no_notes_message(notes))
    n = src["n"]
    target = NOTES_SITE / f"class{n:02d}"
    target.mkdir(parents=True, exist_ok=True)
    # notes_site/ is a website project, so even a single-file render
    # lands in its output-dir (_site/classNN/...), not next to the
    # source index.qmd.
    site_pdf = NOTES_SITE / "_site" / f"class{n:02d}" / "index.pdf"

    original_text = notes.read_text(encoding="utf-8")
    description = qmd.what_we_covered(original_text)

    # The site copy has no ts.css beside it (notes_site/'s own scss
    # already carries the same .ts rules), so its header omits css:.
    header = header_for(src, description=description, css=None)
    text = qmd.replace_front_matter(original_text, header)
    (target / "index.qmd").write_text(text, encoding="utf-8")
    qmd.copy_referenced_images(text, out, target)

    # Render the whole project before attempting a PDF: a full project
    # render cleans output-dir of anything not part of this pass, which
    # is what actually removes a stale PDF left by an earlier publish
    # (rendering the PDF first and the project second would have quarto
    # clean the PDF right back out, since a project render only keeps
    # what its own pass produces).
    proc = subprocess.run(["quarto", "render"], cwd=str(NOTES_SITE),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    if proc.returncode != 0:
        raise SystemExit("quarto render (notes_site) failed:\n"
                         + (proc.stderr or "") + (proc.stdout or ""))

    if args.pdf:
        proc = subprocess.run(["quarto", "render", "index.qmd", "--to", "typst"],
                              cwd=str(target), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode == 0 and site_pdf.exists():
            print(f"  pdf: {site_pdf}")
            header = header_for(src, description=description,
                                extra_links={"PDF": "index.pdf"}, css=None)
            text = qmd.replace_front_matter(original_text, header)
            (target / "index.qmd").write_text(text, encoding="utf-8")
            # A single-file render only touches this page's own output,
            # so it picks up the new link without disturbing the rest of
            # the just-rendered site (or the PDF just produced above).
            proc2 = subprocess.run(
                ["quarto", "render", "index.qmd", "--to", "html"],
                cwd=str(target), capture_output=True, text=True,
                encoding="utf-8", errors="replace")
            if proc2.returncode != 0:
                raise SystemExit(
                    "quarto render (class page, after pdf) failed:\n"
                    + (proc2.stderr or "") + (proc2.stdout or ""))
        else:
            tail = ((proc.stderr or "") + (proc.stdout or ""))[-2000:]
            print("  pdf render failed (best effort; continuing):")
            print(tail)
            # A partial PDF from this failed attempt must not linger
            # next to a page whose header does not link one.
            site_pdf.unlink(missing_ok=True)
            (target / "index.pdf").unlink(missing_ok=True)

    _rebuild_docs()
    print(f"  published: {target}")
    print(f"  site rendered: {DOCS_DIR}")
    return target


def _inside_project(path: Path) -> bool:
    try:
        Path(path).resolve().relative_to(PROJECT_ROOT.resolve())
        return True
    except ValueError:
        return False


def stage_deploy(args) -> None:
    """Mirror the rendered docs/ elsewhere, e.g. a second repo. The normal
    workflow needs no deploy step: docs/ is committed here and GitHub
    Pages serves it directly. This only overwrites files docs/ has; it
    never deletes anything already in the target that docs/ does not."""
    if not DOCS_DIR.exists():
        raise SystemExit(f"{DOCS_DIR} does not exist; run with --publish first")
    dest = Path(args.deploy).resolve()
    if _inside_project(dest):
        raise SystemExit(f"--deploy {dest} resolves inside this project; point "
                         f"it at a checkout outside {PROJECT_ROOT}")
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for p in DOCS_DIR.rglob("*"):
        if p.is_file():
            target = dest / p.relative_to(DOCS_DIR)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
            count += 1
    print(f"  deployed {count} file(s) to {dest}")
    print("  commit and push in that repo to publish the change")


def stage_verify(out: Path, mp4: Path, tj: Path, found: list[dict], src: dict,
                 args) -> None:
    notes = out / "notes.qmd"
    if not notes.exists():
        raise SystemExit(_no_notes_message(notes))
    user = I.verify_message(
        notes=notes, instructor=src["instructor"], deck=src.get("deck"),
        class_rmd=src.get("class_rmd"),
        transcript_text=_transcript_text(tj, found),
        scene_index=SC.index_text(found),
        pronouns=src.get("instructor_pronouns"))
    print("  checking the notes against the transcript")
    run_agent(system_prompt=I.VERIFY_PROMPT, user_text=user,
              ctx=_ctx(out, mp4, tj, found), output_file=notes,
              backend=args.backend, model=args.model,
              frame_model=args.frame_model, revise=True,
              role="verify", log_dir=out / "logs")


def stage_answer(out: Path, mp4: Path, tj: Path, found: list[dict], src: dict,
                 args) -> None:
    notes = out / "notes.qmd"
    if not notes.exists():
        raise SystemExit(_no_notes_message(notes))
    ctx = _ctx(out, mp4, tj, found)
    answers = collect_followup_answers(ctx, notes, _segments(tj))
    todos = count_todos(notes.read_text(encoding="utf-8"))
    if not answers and todos == 0:
        print("  no open questions and no todo comments; nothing to do")
        return
    parts = [f"You previously wrote companion notes to `{notes.resolve()}`."]
    if answers:
        parts.append("The instructor has now answered previously open "
                     f"questions:\n\n{answers}")
    parts.append(
        f"The file contains {todos} <!-- todo --> comment(s). Read the file, "
        f"then: apply the answers above, and review each remaining todo. "
        f"Resolve those you now can (using the answers, the stills, the "
        f"frame-reader, or the class RMD; ask again if needed) and remove "
        f"the resolved comments. Leave genuinely unresolved ones in place.\n\n"
        f"{I._sources_block(src.get('deck'), src.get('class_rmd'))}\n\n"
        f"{I.instructor_line(src['instructor'], src.get('instructor_pronouns'))}")
    run_agent(system_prompt=I.SYSTEM_PROMPT, user_text="\n\n".join(parts),
              ctx=ctx, output_file=notes, backend=args.backend,
              model=args.model, frame_model=args.frame_model, revise=True,
              wait_for_answers=args.wait, role="revise", log_dir=out / "logs")
    mark_answers_applied(ctx, notes)


def stage_render(out: Path, mp4: Path, tj: Path, found: list[dict], src: dict,
                 args) -> bool:
    notes = out / "notes.qmd"
    header = header_for(src)
    text = notes.read_text(encoding="utf-8")
    if not qmd.front_matter_matches(notes, header):
        text = qmd.replace_front_matter(text, header)
        notes.write_text(text, encoding="utf-8")
        print("  front matter did not match the expected header; restored it")

    fences = qmd.executable_fences(text)
    if fences:
        raise SystemExit(
            f"{notes} has an executable code fence ({fences[0]!r}); "
            f"rendering it would run that code. Use an inert fence "
            f"(```r, not ```{{r}}) and fix the file before rendering.")

    if src.get("video_url_template"):
        text = qmd.link_timestamps(text, src["video_url_template"])
        notes.write_text(text, encoding="utf-8")
    ok, log = qmd.render(notes)
    if ok:
        print(f"  quarto render: ok ({out / 'notes.html'})")
        return True
    print("  quarto render failed; asking the agent for one repair round")
    tail = log[-4000:]
    run_agent(
        system_prompt=I.SYSTEM_PROMPT,
        user_text=(f"`quarto render` of `{notes.resolve()}` failed. Fix the "
                   f"Markdown or front matter so it renders, changing no "
                   f"content. The error output:\n\n```\n{tail}\n```"),
        ctx=_ctx(out, mp4, tj, found), output_file=notes,
        backend=args.backend, model=args.model, frame_model=args.frame_model,
        revise=True, role="fix", log_dir=out / "logs")
    ok, log = qmd.render(notes)
    print(f"  quarto render after repair: {'ok' if ok else 'STILL FAILING'}")
    if not ok:
        print(log[-2000:])
    return ok


# -- CLI ---------------------------------------------------------------------

def parse_args(argv: list[str]):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("session_dir")
    p.add_argument("--class-rmd", default=None)
    p.add_argument("--deck", default=None)
    p.add_argument("--instructor", default=None)
    p.add_argument("--instructor-pronouns", default=None,
                   help='e.g. "he/him"; saved in state')
    p.add_argument("--video-url", default=None)
    p.add_argument("--video-url-template", default=None,
                   help="e.g. https://youtu.be/ID?t={seconds}; turns timestamps into links")
    p.add_argument("--answer", action="store_true")
    p.add_argument("--verify", action="store_true", help="run only the checking pass")
    p.add_argument("--no-verify", dest="verify_after", action="store_false", default=True)
    p.add_argument("--regen", action="store_true")
    p.add_argument("--publish", action="store_true",
                   help="land this class's page in notes_site/ and render docs/")
    p.add_argument("--pdf", action="store_true",
                   help="with --publish, also render index.pdf (best effort)")
    p.add_argument("--deploy", metavar="DIR", default=None,
                   help="mirror the rendered docs/ into DIR (optional; docs/ "
                        "must already exist, from --publish now or earlier)")
    p.add_argument("--no-scenes", dest="scenes", action="store_false", default=True)
    p.add_argument("--scene-threshold", type=float, default=0.30)
    p.add_argument("--wait", action="store_true")
    p.add_argument("--backend", default="subscription", choices=BACKENDS)
    p.add_argument("--model", default=None)
    p.add_argument("--frame-model", default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    require_tools(["ffmpeg", "ffprobe", "quarto"])
    args = parse_args(sys.argv[1:] if argv is None else argv)
    session_dir = Path(args.session_dir).resolve()
    out = session_dir / "out"
    mp4, vtt_path = find_media(session_dir)
    state = load_state(out)
    src = resolve_sources(session_dir, args, state)
    save_state(out, {**state, **{k: (str(v) if isinstance(v, Path) else v)
                                 for k, v in src.items() if k in SAVED_KEYS}})
    print(f"Class {src['n']:02d}: {session_dir.name}")
    print(f"  deck: {src['deck'] or 'none'}")
    print(f"  class RMD: {src['class_rmd'] or 'none'}")

    tj = stage_transcript(vtt_path, out)
    found = stage_scenes(mp4, out, args.scenes, args.scene_threshold)
    notes = out / "notes.qmd"

    if args.answer:
        stage_answer(out, mp4, tj, found, src, args)
        stage_render(out, mp4, tj, found, src, args)
    elif args.verify:
        stage_verify(out, mp4, tj, found, src, args)
        stage_render(out, mp4, tj, found, src, args)
    else:
        if notes.exists() and not args.regen:
            print(f"  notes.qmd exists; pass --regen to rewrite, --verify or "
                  f"--answer for a pass")
        else:
            stage_write(out, mp4, tj, found, src, args)
            if args.verify_after:
                stage_verify(out, mp4, tj, found, src, args)
            stage_render(out, mp4, tj, found, src, args)

    if args.publish:
        stage_publish(out, src, args)
    if args.deploy:
        stage_deploy(args)


if __name__ == "__main__":
    main()
