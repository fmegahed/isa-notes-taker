# ISA 401 Session Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A command that turns one recorded ISA 401 class (Zoom MP4 + VTT, the slide deck, the in-class RMD) into a student-facing `notes.qmd` with timestamps, a verify pass, and a question queue.

**Architecture:** A plain directory `isa_notes/` of Python scripts. Five modules are copied verbatim from the upstream clone at `notetaker/` and edited in a handful of named places (LaTeX wording to Quarto, HTML-comment todos, three document-fetch tools removed, one crop tool added). Four new modules do the ISA-specific work: `vtt.py` (Zoom transcript), `scenes.py` (ffmpeg scene stills), `qmd.py` (deck lookup, front matter, timestamp and todo syntax, render check, publish), `instructions.py` (prompts). `session.py` is the CLI and stage orchestrator.

**Tech Stack:** Python 3.14, ffmpeg 9, Quarto 1.10, `claude-agent-sdk` on the Claude Code CLI (subscription backend), Pillow for crops. No test framework: plain assertion scripts run with `python`.

**Spec:** `docs/superpowers/specs/2026-09-04-isa401-session-notes-design.md`

## Global Constraints

- Python 3.10+ syntax (`X | None`, `match`) is fine; the machine runs 3.14.
- No em dashes in any prose a student can see, and none in prompt text that asks the model to write prose.
- No test calls a model. Tests run with `python isa_notes/tests/test_x.py` and must not touch `sessions/`.
- Every file under `isa_notes/` is committed; `sessions/`, `isa401/`, `class_code/`, `notetaker/`, `lectures/` are gitignored and must stay so.
- The upstream clone at `notetaker/` is read-only reference; never edit it.
- Commit messages end with the two attribution lines used in this repo (see any existing commit: `git log -1`).
- Run scripts from the project root: `python isa_notes/session.py sessions/class03`. `isa_notes/` is not a package; each script inserts its own directory on `sys.path` so the copied modules import each other by bare name exactly as upstream does.

---

## File structure

| File | Responsibility |
|---|---|
| `isa_notes/claude_backend.py` | copy of upstream; runs the agent loop on the subscription backend |
| `isa_notes/notes_tools.py` | copy of upstream; tool specs and handlers, question broker, `NotesToolContext` |
| `isa_notes/agent_log.py` | copy of upstream, unchanged |
| `isa_notes/media.py` | copy of upstream, unchanged |
| `isa_notes/usage.py` | copy of upstream, unchanged |
| `isa_notes/vtt.py` | Zoom VTT to `transcript.json` |
| `isa_notes/scenes.py` | scene stills, `scenes.json`, transcript marks, scene index text |
| `isa_notes/qmd.py` | deck and class RMD lookup, deck metadata, front matter, `[hh:mm:ss]{.ts}` and `<!-- todo -->` syntax, timestamp linking, render check, publish |
| `isa_notes/instructions.py` | writer system prompt, verify prompt, user message builders |
| `isa_notes/session.py` | CLI, `state.json`, stage orchestration |
| `isa_notes/ts.css` | timestamp styling |
| `isa_notes/requirements.txt` | `claude-agent-sdk`, `anyio`, `pillow` |
| `isa_notes/README.md` | how to run one session |
| `isa_notes/tests/test_*.py` | one script per module |

---

### Task 1: Scaffold, vendored copies, dependency install

**Files:**
- Create: `isa_notes/claude_backend.py`, `isa_notes/notes_tools.py`, `isa_notes/agent_log.py`, `isa_notes/media.py`, `isa_notes/usage.py` (copies)
- Create: `isa_notes/requirements.txt`
- Create: `isa_notes/tests/test_vendor.py`

**Interfaces:**
- Produces: importable modules `claude_backend`, `notes_tools`, `agent_log`, `media`, `usage` when `isa_notes/` is on `sys.path`. `notes_tools.build_tools(ctx)` returns no `fetch_document`, `search_document`, or `view_pdf_page` spec; `notes_tools.build_handlers(ctx)` has no such keys.

- [ ] **Step 1: Copy the five modules and write requirements**

```bash
mkdir -p isa_notes/tests
cp notetaker/claude_backend.py notetaker/notes_tools.py notetaker/agent_log.py notetaker/media.py notetaker/usage.py isa_notes/
printf '%s\n' 'claude-agent-sdk>=0.2' 'anyio>=4' 'pillow>=10' > isa_notes/requirements.txt
pip install -r isa_notes/requirements.txt
```

- [ ] **Step 2: Write the failing test**

`isa_notes/tests/test_vendor.py`:

```python
"""The vendored upstream modules import on their own, with the document-fetch
tools gone. fetch.py was not copied (it drags in PDF libraries and a paper
cache this tool has no use for), so the three tools built on it have to be
removed rather than left to fail at first call."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import claude_backend as CB          # noqa: E402
import notes_tools as NT             # noqa: E402

ctx = NT.NotesToolContext(refs_dir=HERE / "unused")
names = {t["name"] for t in NT.build_tools(ctx)}
for gone in ("fetch_document", "search_document", "view_pdf_page"):
    assert gone not in names, f"{gone} still offered"
    assert gone not in NT.build_handlers(ctx), f"{gone} still handled"
for kept in ("clarify_transcript", "ask_user", "get_user_answers"):
    assert kept in names and kept in NT.build_handlers(ctx), kept
assert "get_frame" not in names, "no video, so no frame tool"
ctx_v = NT.NotesToolContext(refs_dir=HERE / "unused", video_path=Path("x.mp4"))
assert "get_frame" in {t["name"] for t in NT.build_tools(ctx_v)}
assert "subscription" in CB.BACKENDS
print("vendored modules import; fetch tools removed; question and frame tools kept")
```

- [ ] **Step 3: Run it to see it fail**

Run: `python isa_notes/tests/test_vendor.py`
Expected: `ModuleNotFoundError: No module named 'fetch'`

- [ ] **Step 4: Remove the fetch import and the three tools from `isa_notes/notes_tools.py`**

Edit the copy only. Four deletions:

1. Delete the line `from fetch import describe_assets, fetch_reference`.
2. In `build_tools(ctx)`, delete the three dict literals whose `"name"` is `"fetch_document"`, `"search_document"`, and `"view_pdf_page"` (each is one element of the list being built; delete the whole element including its trailing comma).
3. In `build_handlers(ctx)`, delete the three nested functions `fetch_document`, `search_document`, and `view_pdf_page`, and the helper `_file_roots` if nothing else uses it (grep for `_file_roots` after deleting; if only those three used it, delete it).
4. In the `handlers: dict[str, Handler] = {` literal at the end of `build_handlers`, delete the lines for `"fetch_document"`, `"search_document"`, `"view_pdf_page"`.

Then: `grep -n "fetch_reference\|describe_assets\|_file_roots\|search_document\|view_pdf_page\|fetch_document" isa_notes/notes_tools.py` must print nothing.

- [ ] **Step 5: Run the test**

Run: `python isa_notes/tests/test_vendor.py`
Expected: the printed line, exit 0.

- [ ] **Step 6: Commit**

```bash
git add isa_notes
git commit -m "Vendor upstream agent modules; drop document-fetch tools"
```

---

### Task 2: Quarto wording and HTML-comment todos in the vendored modules

**Files:**
- Modify: `isa_notes/claude_backend.py` (`ASYNC_QA_INSTRUCTION`, `count_todos`, `_write_instruction`, `_revision_message`, `FRAME_DELEGATION_SUBSCRIPTION`)
- Modify: `isa_notes/notes_tools.py` (`_marker`, `FRAME_READER_PROMPT`)
- Create: `isa_notes/tests/test_todo_syntax.py`

**Interfaces:**
- Produces: `claude_backend.count_todos(text) -> int` counts `<!-- todo: ... -->` comments. `notes_tools` marker text is `<!-- todo: awaiting answer #N @ hh:mm:ss -->`. Prompts contain no `\todo` and no "LaTeX".

- [ ] **Step 1: Write the failing test**

`isa_notes/tests/test_todo_syntax.py`:

```python
"""The notes are Quarto Markdown, so a todo is an HTML comment students never
see, and the agent is told to write Markdown, not LaTeX. Every string the
vendored modules put in front of the model has to agree with that."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import claude_backend as CB   # noqa: E402
import notes_tools as NT      # noqa: E402

assert CB.count_todos("a <!-- todo: x --> b <!--todo: y-->") == 2
assert CB.count_todos("<!-- TODO: z -->") == 1, "case-insensitive"
assert CB.count_todos(r"\todo{old}") == 0, "LaTeX markers are not ours"
assert CB.count_todos("<!-- note -->") == 0

for name, text in (("ASYNC_QA_INSTRUCTION", CB.ASYNC_QA_INSTRUCTION),
                   ("FRAME_DELEGATION_SUBSCRIPTION", CB.FRAME_DELEGATION_SUBSCRIPTION),
                   ("FRAME_READER_PROMPT", NT.FRAME_READER_PROMPT),
                   ("write", CB._write_instruction("subscription", Path("n.qmd"))),
                   ("revise", CB._write_instruction("subscription", Path("n.qmd"), True)),
                   ("revision", CB._revision_message([]))):
    assert "\\todo" not in text, name
    assert "LaTeX" not in text and "latex" not in text, name
    assert "—" not in text, f"em dash in {name}"
assert "<!-- todo: awaiting answer #N @ hh:mm:ss -->" in CB.ASYNC_QA_INSTRUCTION
assert "Quarto" in CB._write_instruction("subscription", Path("n.qmd"))
assert "RStudio" in NT.FRAME_READER_PROMPT or "screen" in NT.FRAME_READER_PROMPT

# The answers block a follow-up run hands the agent is prompt text too.
sample = [
    {"id": 1, "kind": "clarify", "text": "the tidy verse", "guess": "the tidyverse",
     "answer": "", "timestamp": "00:10:00"},
    {"id": 2, "kind": "clarify", "text": "read see ess vee", "guess": "read_csv",
     "answer": "readr::read_csv", "timestamp": "00:11:00"},
    {"id": 3, "kind": "ask_user", "text": "Keep the detour?", "guess": "kept it",
     "answer": "", "deferred": True},
    {"id": 4, "kind": "ask_user", "text": "Which file?", "guess": "", "answer": "jobs.csv"},
]
block = NT.format_answers(sample)
assert "\\todo" not in block and "—" not in block, block
assert "todo comment" in block
assert NT.format_answers([]) == ""
print("todos are HTML comments; prompts speak Quarto")
```

- [ ] **Step 2: Run it to see it fail**

Run: `python isa_notes/tests/test_todo_syntax.py`
Expected: `AssertionError` on the first `count_todos` line.

- [ ] **Step 3: Edit `isa_notes/claude_backend.py`**

Replace `count_todos`:

```python
_TODO_RE = re.compile(r"<!--\s*todo\b", re.IGNORECASE)


def count_todos(text: str) -> int:
    return len(_TODO_RE.findall(text))
```

Replace the body of `ASYNC_QA_INSTRUCTION` with:

```python
ASYNC_QA_INSTRUCTION = """

Questions to the user (ask_user, clarify_transcript) are asynchronous: the
tool queues the question and returns immediately, and the user answers while
you keep working. Do not stop and wait for an answer. Adopt your best
provisional version, mark the spot with
<!-- todo: awaiting answer #N @ hh:mm:ss --> on its own line, and continue.
Always give the question a timestamp, copied from the transcript line it
arose from: it is how the user finds the moment in the recording, and a
question they cannot locate is a question they cannot answer. Tell ask_user
what your provisional choice was, and clarify_transcript your best guess. The
answer may come back in a follow-up run, where you are a fresh context with
no memory of either, and a reply of "yes, that one" is only usable if you are
told what you proposed. Call get_user_answers before you finish, to
incorporate answers that have already arrived; answers that arrive by the end
of your pass are delivered in a follow-up turn, in which you revise the file
(apply the answers and remove the resolved todo comments) rather than
rewriting it. Questions the user has not answered (or has deferred) by then
stay open: keep their todo comments; a later follow-up run resolves them."""
```

Replace `_revision_message`:

```python
def _revision_message(items: list[dict]) -> str:
    return (
        "The user has answered your earlier questions:\n\n"
        + format_answers(items)
        + "\n\nRevise the notes file accordingly: apply the corrections, "
          "remove the <!-- todo --> comments that are now resolved, and "
          "leave everything else untouched. Reply with a one-line summary "
          "of what you changed."
    )
```

Replace `_write_instruction`:

```python
def _write_instruction(backend: str, output_file: Path,
                       revise: bool = False) -> str:
    if revise:
        base = (
            f"\n\n---\n**Output**: revise the existing file `{output_file}` "
            f"in place. Read it first, then apply targeted edits rather than "
            f"rewriting the whole file, and do NOT include the notes in your "
            f"reply text. Reply with a one-line summary of the edits."
        )
        if backend == "api":
            return base + (" Use read_notes and edit_notes (write_notes only "
                           "if a full rewrite is unavoidable).")
        if backend == "subscription":
            return base + " Use your Read and Edit tools."
        return base
    base = (
        f"\n\n---\n**Output**: write the final Quarto Markdown to the file "
        f"`{output_file}`. Do NOT include the notes in your reply text. "
        f"Build the file incrementally: work through the transcript in "
        f"order, 10 to 15 minutes of class at a time, appending each "
        f"completed part before moving on. The final third of the class "
        f"deserves the same detail as the first. Once the file is complete, "
        f"reply with a one-line confirmation."
    )
    if backend == "api":
        return base + (
            " Use the write_notes tool: one call with mode=\"overwrite\" "
            "first; if the document does not fit in a single call, continue "
            "with mode=\"append\" calls."
        )
    if backend == "subscription":
        return base + " Use your Write tool (and Edit for corrections)."
    return base
```

Replace `FRAME_DELEGATION_SUBSCRIPTION`:

```python
FRAME_DELEGATION_SUBSCRIPTION = """

Frame analysis: video frames are token-expensive for you. By default, delegate
frame reading to the 'frame-reader' subagent (via the Task tool): tell it the
timestamp(s), what the transcript says around that moment, and what to look
for; it will fetch and study the frames and report what is on screen. Only
call get_frame yourself when the subagent's report is ambiguous, incomplete,
or implausible and the passage is important."""
```

- [ ] **Step 4: Edit `isa_notes/notes_tools.py`**

Replace `format_answers` (module level, just above `build_tools`):

```python
def format_answers(items: list[dict]) -> str:
    """Render answered questions for delivery to the agent.

    A follow-up run is a fresh context: the agent no longer remembers what it
    asked or what it provisionally wrote, and only has this block plus the
    todo comment to work from. So every answer restates the question and the
    agent's own guess; without them a bare answer like "yes, the second one"
    is unusable."""
    lines = []
    for q in items:
        at = f" [{q['timestamp']}]" if q.get("timestamp") else ""
        guess = q.get("guess") or ""
        if q["kind"] == "clarify":
            head = f"- Answer #{q['id']}{at}: transcript read \"{q['text']}\""
            head += (f"; your guess was \"{guess}\"." if guess
                     else " (you made no guess).")
        else:
            head = f"- Answer #{q['id']}{at}: you asked: \"{q['text']}\""
            head += (f"; provisionally you used: {guess}." if guess else ".")
        lines.append(head)

        if q.get("deferred"):
            lines.append("  DEFERRED by the user: keep your provisional "
                         "version and its todo comment; a later follow-up "
                         "run may resolve it.")
        elif q["kind"] == "clarify":
            final = q["answer"] or guess
            if final == guess:
                lines.append(f"  CONFIRMED: it reads \"{final}\". Remove the "
                             f"matching todo comment.")
            else:
                lines.append(f"  CORRECTED: it should read \"{final}\", not "
                             f"\"{guess}\". Fix the text and remove the "
                             f"matching todo comment.")
        else:
            lines.append(f"  User's answer: {q['answer']}")
    return "\n".join(lines)
```

Replace `_marker` inside `build_handlers`:

```python
    def _marker(q: dict) -> str:
        at = f" @ {q['timestamp']}" if q.get("timestamp") else ""
        return f"<!-- todo: awaiting answer #{q['id']}{at} -->"
```

Replace `FRAME_READER_PROMPT`:

```python
FRAME_READER_PROMPT = """You are a frame-reading assistant for recordings of a
business analytics class. The screen shows one of: RStudio (source pane,
console, environment, viewer), a rendered R Markdown page, slides, a browser,
or a GUI tool such as Tableau, Power BI, Flourish, or DataWrapper. You are
given context and one or more video frames (or a get_frame tool to fetch
them; it may return the image directly or save it to a file for you to open).

Produce a report on what is shown that is relevant to the context:
- Transcribe visible code and console output exactly, in a fenced block,
  including error messages. Say which pane it is in.
- For a GUI, name the window, menu, dialog, field names, and what is
  selected or highlighted, in the order a user would read them.
- For a chart or table, describe the type, axes, fields, and any visible
  values or labels.
- Say explicitly where content is cut off by the frame edge, covered by
  another window, blurred, or too small to read, and which parts of your
  transcription are uncertain because of it.
- If the frame shows a screen share by someone other than the instructor
  (a name overlay that is not the instructor's, or a different desktop),
  say so first: that frame must not be embedded in the notes.

Frames may be mid-transition; when you can fetch frames yourself, try nearby
timestamps to get a clearer view before reporting. Report only what is
visible. Never invent or complete code or values. Flagging something as
unreadable is always better than guessing."""
```

- [ ] **Step 5: Run the test and the vendor test**

Run: `python isa_notes/tests/test_todo_syntax.py && python isa_notes/tests/test_vendor.py`
Expected: both print their line, exit 0.

- [ ] **Step 6: Commit**

```bash
git add isa_notes
git commit -m "Vendored modules speak Quarto; todos are HTML comments"
```

---

### Task 3: Zoom VTT to transcript.json

**Files:**
- Create: `isa_notes/vtt.py`
- Create: `isa_notes/tests/test_vtt.py`

**Interfaces:**
- Produces: `vtt.parse_vtt(text: str) -> list[dict]` of cues `{"start": float, "end": float, "speaker": str, "text": str}`; `vtt.merge_cues(cues, gap=1.5, max_len=30.0) -> list[dict]` same schema; `vtt.write_transcript(vtt_path: Path, out_path: Path) -> int` writes `{"segments": [...], "metadata": {"source": str, "cues": int}}` and returns the segment count.

- [ ] **Step 1: Write the failing test**

`isa_notes/tests/test_vtt.py`:

```python
"""Zoom's audio_transcript.vtt: WEBVTT header, then numbered cues with
hh:mm:ss.mmm --> hh:mm:ss.mmm and one text line prefixed "Speaker Name: ".
Merging turns eight-second slivers into readable paragraphs without losing
the start time of the first cue, and stops at 30 s so a timestamp copied
from the transcript still lands within half a minute of the moment."""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import vtt   # noqa: E402

SAMPLE = """WEBVTT

1
00:00:02.900 --> 00:00:22.430
Fadel Megahed: Okay, so just as a reminder.

2
00:00:22.570 --> 00:00:30.360
Fadel Megahed: This week, we're gonna talk more about R.

3
00:00:35.000 --> 00:00:41.040
Fadel Megahed: After a gap.

4
00:00:41.100 --> 00:00:45.000
Guest: A different speaker.

5
00:00:45.100 --> 00:00:50.000
No colon here at all

6
00:01:00.000 --> 00:01:20.000
Fadel Megahed: Long one.

7
00:01:20.500 --> 00:01:40.000
Fadel Megahed: Would push the merged segment past 30 s.
"""

cues = vtt.parse_vtt(SAMPLE)
assert len(cues) == 7
assert cues[0]["start"] == 2.9 and cues[0]["end"] == 22.43
assert cues[0]["speaker"] == "Fadel Megahed"
assert cues[0]["text"] == "Okay, so just as a reminder."
assert cues[4]["speaker"] == "" and cues[4]["text"] == "No colon here at all"
print("cues parsed with times, speaker, text")

merged = vtt.merge_cues(cues)
# 1+2 merge (gap 0.14 s, same speaker); 3 stands alone (gap 4.6 s);
# 4 is another speaker; 5 has no speaker; 6 and 7 would exceed 30 s.
assert [m["start"] for m in merged] == [2.9, 35.0, 41.1, 45.1, 60.0, 80.5], \
    [m["start"] for m in merged]
assert merged[0]["end"] == 30.36
assert merged[0]["text"] == ("Okay, so just as a reminder. This week, we're "
                             "gonna talk more about R.")
print("merge joins close cues from one speaker, keeps the first start")

with tempfile.TemporaryDirectory() as d:
    src = Path(d) / "x.transcript.vtt"
    src.write_text(SAMPLE, encoding="utf-8")
    out = Path(d) / "transcript.json"
    n = vtt.write_transcript(src, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert n == 6 and len(data["segments"]) == 6
    assert data["metadata"]["cues"] == 7
    assert set(data["segments"][0]) == {"start", "end", "speaker", "text"}
print("transcript.json written in the upstream segment schema")
```

- [ ] **Step 2: Run it to see it fail**

Run: `python isa_notes/tests/test_vtt.py`
Expected: `ModuleNotFoundError: No module named 'vtt'`

- [ ] **Step 3: Write `isa_notes/vtt.py`**

```python
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
```

- [ ] **Step 4: Run the test**

Run: `python isa_notes/tests/test_vtt.py`
Expected: three printed lines, exit 0.

- [ ] **Step 5: Try it on a real file (no assertion, just look)**

Run: `python -c "import sys; sys.path.insert(0,'isa_notes'); import vtt, glob, pathlib; p=glob.glob('sessions/class03/*.vtt')[0]; print(vtt.write_transcript(pathlib.Path(p), pathlib.Path('sessions/class03/out/transcript.json')))"`
Expected: a number between 150 and 400. Then delete `sessions/class03/out/` so the session stage runs fresh later: `rm -r sessions/class03/out`.

- [ ] **Step 6: Commit**

```bash
git add isa_notes/vtt.py isa_notes/tests/test_vtt.py
git commit -m "Parse Zoom VTT into transcript.json"
```

---

### Task 4: Scene stills

**Files:**
- Create: `isa_notes/scenes.py`
- Create: `isa_notes/tests/test_scenes.py`

**Interfaces:**
- Consumes: `media.format_timestamp(seconds) -> "hh:mm:ss"`, `media.format_transcript(segments, marks)`.
- Produces: `scenes.detect(video: Path, out_dir: Path, threshold=0.30, max_scenes=400) -> list[dict]` writing `out_dir/scene-NNN.jpg` and `out_dir/scenes.json`; each dict is `{"id": int, "path": str (absolute), "start": float, "end": float}` with scene 1 always at t=0. `scenes.load(out_dir) -> list[dict]`. `scenes.marks(scenes) -> list[tuple[float, str]]` for `format_transcript`. `scenes.index_text(scenes) -> str` for the prompt.

- [ ] **Step 1: Write the failing test**

`isa_notes/tests/test_scenes.py`:

```python
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
```

- [ ] **Step 2: Run it to see it fail**

Run: `python isa_notes/tests/test_scenes.py`
Expected: `ModuleNotFoundError: No module named 'scenes'`

- [ ] **Step 3: Write `isa_notes/scenes.py`**

```python
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

_PTS = re.compile(r"pts_time:\s*([0-9.]+)")


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
    pattern = tmp_dir / "cut-%04d.jpg"
    vf = f"scale=960:-2,select=gt(scene\\,{threshold:.3f}),showinfo"
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "info", "-i", str(video), "-vf", vf,
         "-fps_mode", "vfr", "-q:v", "3", str(pattern)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    times = [float(m.group(1)) for m in _PTS.finditer(proc.stderr)]
    files = sorted(tmp_dir.glob("cut-*.jpg"))
    return list(zip(times, files))


def detect(video: Path, out_dir: Path, threshold: float = 0.30,
           max_scenes: int = 400) -> list[dict]:
    video = Path(video).resolve()
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    tmp = out_dir / "_tmp"
    tmp.mkdir()

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

    cuts = cuts[:max_scenes - 1]
    duration = _duration(video)
    starts: list[tuple[float, Path]] = []
    first = out_dir / "scene-001.jpg"
    if _first_frame(video, first):
        starts.append((0.0, first))
    for n, (at, src) in enumerate(cuts, start=len(starts) + 1):
        dest = out_dir / f"scene-{n:03d}.jpg"
        shutil.move(str(src), dest)
        starts.append((at, dest))
    shutil.rmtree(tmp, ignore_errors=True)

    result = []
    for i, (at, path) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else duration
        result.append({"id": i + 1, "path": str(path.resolve()),
                       "start": round(at, 3), "end": round(end, 3)})
    (out_dir / "scenes.json").write_text(json.dumps(result, indent=1))
    return result


def load(out_dir: Path) -> list[dict]:
    f = Path(out_dir) / "scenes.json"
    return json.loads(f.read_text()) if f.exists() else []


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
```

- [ ] **Step 4: Run the test**

Run: `python isa_notes/tests/test_scenes.py`
Expected: three printed lines, exit 0. If the first-frame assertion on `lines[1]` fails because `format_timestamp(0.5)` rounds to `00:00:01`, the test already accepts both.

- [ ] **Step 5: Commit**

```bash
git add isa_notes/scenes.py isa_notes/tests/test_scenes.py
git commit -m "Scene stills from ffmpeg scene changes, spliced into the transcript"
```

---

### Task 5: Quarto helpers: deck lookup, front matter, timestamps, todos, render, publish

**Files:**
- Create: `isa_notes/qmd.py`
- Create: `isa_notes/ts.css`
- Create: `isa_notes/tests/test_qmd.py`

**Interfaces:**
- Produces:
  - `qmd.class_number(session_dir: Path) -> int` from `classNN`.
  - `qmd.find_deck(n: int, isa401_root: Path) -> Path | None`; `qmd.find_class_rmd(n: int, class_code_root: Path) -> Path | None`.
  - `qmd.deck_meta(deck: Path) -> dict` with keys `title`, `subtitle` (R inline code and HTML stripped).
  - `qmd.zoom_date(name: str) -> str | None` `"YYYY-MM-DD"` from `GMT20260831-123000...`.
  - `qmd.front_matter(title, subtitle, date, links: dict[str, str | None], note: str) -> str`.
  - `qmd.ensure_front_matter(path: Path, header: str) -> bool` prepends if missing; returns whether it changed the file.
  - `qmd.TS_RE`, `qmd.TODO_RE`; `qmd.timestamps(text) -> list[str]`; `qmd.link_timestamps(text, template: str) -> str`.
  - `qmd.referenced_images(text) -> list[str]`.
  - `qmd.render(path: Path) -> tuple[bool, str]`.
  - `qmd.publish(notes: Path, dest: Path) -> list[Path]`.

- [ ] **Step 1: Write the failing test**

`isa_notes/tests/test_qmd.py`:

```python
"""The Quarto side: where a session's deck and class code live, what goes in
the front matter, the two bits of syntax the model writes ([hh:mm:ss]{.ts}
and <!-- todo -->), and copying a finished page out."""
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import qmd   # noqa: E402

DECK = '''---
title: "ISA 401: Business Intelligence & Data Visualization"
subtitle: '03: `r paste0("<span>", fontawesome::fa("r-project"), "</span>")` Foundations'
author: 'x'
date: "Fall 2026"
output:
  xaringan::moon_reader:
    self_contained: true
---

# Slide
'''

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "sessions" / "class03").mkdir(parents=True)
    assert qmd.class_number(d / "sessions" / "class03") == 3
    deck_dir = d / "isa401" / "lectures" / "03_r_foundations"
    deck_dir.mkdir(parents=True)
    deck = deck_dir / "03_r_foundations.Rmd"
    deck.write_text(DECK, encoding="utf-8")
    assert qmd.find_deck(3, d / "isa401") == deck
    assert qmd.find_deck(9, d / "isa401") is None
    md = d / "class_code" / "markdowns"
    md.mkdir(parents=True)
    (md / "03_r_basics.Rmd").write_text("x")
    (md / "class04.Rmd").write_text("x")
    assert qmd.find_class_rmd(3, d / "class_code") == md / "03_r_basics.Rmd"
    assert qmd.find_class_rmd(4, d / "class_code") == md / "class04.Rmd"
    assert qmd.find_class_rmd(5, d / "class_code") is None
    print("deck and class RMD found by class number")

    meta = qmd.deck_meta(deck)
    assert meta["title"] == "ISA 401: Business Intelligence & Data Visualization"
    assert meta["subtitle"] == "03: Foundations", meta
    assert qmd.zoom_date("GMT20260831-123000_Recording_2426x1516.mp4") == "2026-08-31"
    assert qmd.zoom_date("nope.mp4") is None
    print("deck metadata and Zoom date parsed")

    fm = qmd.front_matter("T", "S", "2026-08-31",
                          {"Slides": "https://s", "Class code": None,
                           "Recording": "https://z"},
                          "Timestamps are hh:mm:ss into the recording.")
    assert fm.startswith("---\ntitle:") and "engine: markdown" in fm
    assert "css: ts.css" in fm and "[Slides](https://s)" in fm
    assert "Class code" not in fm, "links without a URL are dropped"
    assert "—" not in fm
    notes = d / "notes.qmd"
    notes.write_text("# Body\n", encoding="utf-8")
    assert qmd.ensure_front_matter(notes, fm) is True
    assert notes.read_text(encoding="utf-8").startswith(fm)
    assert qmd.ensure_front_matter(notes, fm) is False
    print("front matter assembled and prepended once")

    body = ("[00:12:34]{.ts} A paragraph.\n\n<!-- todo: check this @ 00:13:00 -->\n"
            "[01:02:03]{.ts} Another.\n![](scenes/scene-041.jpg)\n"
            "![alt](crops/crop-002.jpg){width=60%}\n")
    assert qmd.timestamps(body) == ["00:12:34", "01:02:03"]
    assert len(qmd.TODO_RE.findall(body)) == 1
    linked = qmd.link_timestamps(body, "https://youtu.be/ID?t={seconds}")
    assert "[[00:12:34](https://youtu.be/ID?t=754)]{.ts}" in linked, linked
    assert "[[01:02:03](https://youtu.be/ID?t=3723)]{.ts}" in linked
    assert qmd.referenced_images(body) == ["scenes/scene-041.jpg", "crops/crop-002.jpg"]
    print("timestamp and todo syntax; timestamp linking")

    out = d / "out"
    out.mkdir()
    (out / "scenes").mkdir()
    (out / "scenes" / "scene-041.jpg").write_bytes(b"x")
    (out / "notes.qmd").write_text(fm + "\n![](scenes/scene-041.jpg)\n", encoding="utf-8")
    (out / "ts.css").write_text(".ts{}")
    copied = qmd.publish(out / "notes.qmd", d / "site" / "class03")
    names = sorted(p.relative_to(d / "site" / "class03").as_posix() for p in copied)
    assert names == ["notes.qmd", "scenes/scene-041.jpg", "ts.css"], names
    print("publish copies the page, its css, and referenced images")

    ok, log = qmd.render(out / "notes.qmd")
    assert ok, log
    assert (out / "notes.html").exists()
    print("quarto render passes on a minimal page")
```

- [ ] **Step 2: Run it to see it fail**

Run: `python isa_notes/tests/test_qmd.py`
Expected: `ModuleNotFoundError: No module named 'qmd'`

- [ ] **Step 3: Write `isa_notes/ts.css`**

```css
/* Timestamps into the class recording, set inline before the paragraph they
   mark: quiet enough to read past, there when wanted. */
.ts {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.8em;
  color: #6c757d;
  margin-right: 0.4em;
}
.ts a { color: inherit; text-decoration: none; border-bottom: 1px dotted #6c757d; }
```

- [ ] **Step 4: Write `isa_notes/qmd.py`**

```python
"""qmd.py: the Quarto side of a session's notes.

Where the deck and the class code for class NN live, what the page's front
matter says, the two pieces of syntax the model writes ([hh:mm:ss]{.ts} for
a paragraph's start in the recording and <!-- todo: ... --> for a note to the
instructor), turning timestamps into links when the host supports it, the
render check, and copying a finished page out to the site.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from media import parse_timestamp

TS_RE = re.compile(r"\[(\d{2}:\d{2}:\d{2})\]\{\.ts\}")
TODO_RE = re.compile(r"<!--\s*todo\b.*?-->", re.IGNORECASE | re.DOTALL)
_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
_CLASS_RE = re.compile(r"class0*(\d+)$", re.IGNORECASE)
_ZOOM_RE = re.compile(r"GMT(\d{4})(\d{2})(\d{2})-\d{6}")
_R_INLINE = re.compile(r"`r\s[^`]*`")
_HTML = re.compile(r"<[^>]+>")


def class_number(session_dir: Path) -> int:
    m = _CLASS_RE.search(Path(session_dir).name)
    if not m:
        raise SystemExit(f"session folder must be named classNN, got "
                         f"{Path(session_dir).name!r}")
    return int(m.group(1))


def find_deck(n: int, isa401_root: Path) -> Path | None:
    hits = sorted(Path(isa401_root).glob(f"lectures/{n:02d}_*/{n:02d}_*.Rmd"))
    return hits[0] if len(hits) == 1 else None


def find_class_rmd(n: int, class_code_root: Path) -> Path | None:
    md = Path(class_code_root) / "markdowns"
    hits = sorted(set(md.glob(f"{n:02d}_*.Rmd")) | set(md.glob(f"class{n:02d}*.Rmd"))
                  | set(md.glob(f"class{n}.Rmd")))
    return hits[0] if len(hits) == 1 else None


def _yaml_scalar(block: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.+?)\s*$", block, re.MULTILINE)
    if not m:
        return ""
    v = m.group(1).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    v = _HTML.sub("", _R_INLINE.sub("", v))
    return re.sub(r"\s+", " ", v).strip()


def deck_meta(deck: Path) -> dict:
    text = Path(deck).read_text(encoding="utf-8", errors="replace")
    m = re.match(r"---\s*\n(.*?)\n---", text, re.DOTALL)
    block = m.group(1) if m else ""
    return {"title": _yaml_scalar(block, "title"),
            "subtitle": _yaml_scalar(block, "subtitle")}


def zoom_date(name: str) -> str | None:
    m = _ZOOM_RE.search(name)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def front_matter(title: str, subtitle: str, date: str | None,
                 links: dict[str, str | None], note: str) -> str:
    def q(s: str) -> str:
        return '"' + s.replace('"', '\\"') + '"'
    lines = ["---", f"title: {q(title)}"]
    if subtitle:
        lines.append(f"subtitle: {q(subtitle)}")
    if date:
        lines.append(f"date: {q(date)}")
    lines += ["engine: markdown", "format:", "  html:", "    toc: true",
              "    toc-depth: 3", "    css: ts.css", "    code-copy: true",
              "---", ""]
    items = [f"[{k}]({v})" for k, v in links.items() if v]
    if items:
        lines.append(" | ".join(items) + "  ")
    if note:
        lines.append(note)
    lines.append("")
    return "\n".join(lines) + "\n"


def ensure_front_matter(path: Path, header: str) -> bool:
    text = Path(path).read_text(encoding="utf-8")
    if text.lstrip().startswith("---"):
        return False
    Path(path).write_text(header + "\n" + text, encoding="utf-8")
    return True


def timestamps(text: str) -> list[str]:
    return TS_RE.findall(text)


def link_timestamps(text: str, template: str) -> str:
    def sub(m: re.Match) -> str:
        secs = int(parse_timestamp(m.group(1)) or 0)
        return f"[[{m.group(1)}]({template.format(seconds=secs)})]{{.ts}}"
    return TS_RE.sub(sub, text)


def referenced_images(text: str) -> list[str]:
    seen: list[str] = []
    for p in _IMG_RE.findall(text):
        if p not in seen and not p.startswith(("http://", "https://")):
            seen.append(p)
    return seen


def render(path: Path) -> tuple[bool, str]:
    proc = subprocess.run(["quarto", "render", str(Path(path).name), "--to", "html"],
                          cwd=str(Path(path).parent), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    return proc.returncode == 0, (proc.stderr or "") + (proc.stdout or "")


def publish(notes: Path, dest: Path) -> list[Path]:
    notes = Path(notes)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for rel in ["notes.qmd", "ts.css"] + referenced_images(
            notes.read_text(encoding="utf-8")):
        src = notes.parent / rel
        if not src.exists():
            print(f"  (publish: {rel} is referenced but missing)")
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(target)
    return copied
```

- [ ] **Step 5: Run the test**

Run: `python isa_notes/tests/test_qmd.py`
Expected: six printed lines, exit 0. The last check runs Quarto for real and takes a few seconds.

- [ ] **Step 6: Commit**

```bash
git add isa_notes/qmd.py isa_notes/ts.css isa_notes/tests/test_qmd.py
git commit -m "Quarto helpers: deck lookup, front matter, timestamp and todo syntax, publish"
```

---

### Task 6: `crop_still` tool for embedding a region of a scene

**Files:**
- Modify: `isa_notes/notes_tools.py` (`build_tools`, `build_handlers`)
- Create: `isa_notes/tests/test_crop.py`

**Interfaces:**
- Consumes: `ctx.boards` (the upstream field, reused to hold the scene list from `scenes.load`), `ctx.diagrams_dir` (reused as the crops directory `out/crops`).
- Produces: tool `crop_still` with input `{scene: int, x, y, width, height: fractions 0..1}`; writes `crops/crop-NNN.jpg` and returns the path relative to the notes file plus the image inline. Offered only when `ctx.boards` is non-empty and `ctx.diagrams_dir` is set.

- [ ] **Step 1: Write the failing test**

`isa_notes/tests/test_crop.py`:

```python
"""A GUI step is worth a picture only if the picture shows the dialog and not
the whole desktop. crop_still cuts a fractional box out of a scene still at
native resolution and hands back a path the notes can embed."""
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import notes_tools as NT   # noqa: E402

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    still = d / "scenes" / "scene-007.jpg"
    still.parent.mkdir()
    Image.new("RGB", (400, 200), "white").save(still)
    ctx = NT.NotesToolContext(refs_dir=d, boards=[
        {"id": 7, "path": str(still), "start": 1.0, "end": 2.0}],
        diagrams_dir=d / "crops")
    names = {t["name"] for t in NT.build_tools(ctx)}
    assert "crop_still" in names and "crop_board" not in names
    assert "check_diagram" not in names
    h = NT.build_handlers(ctx)["crop_still"]

    r = h({"scene": 7, "x": 0.5, "y": 0.0, "width": 0.5, "height": 0.5})
    assert not r.is_error, r.content
    text = r.content[0]["text"] if isinstance(r.content, list) else r.content
    assert "crops/crop-001.jpg" in text, text
    im = Image.open(d / "crops" / "crop-001.jpg")
    assert im.size == (200, 100), im.size
    print("crop written at native resolution, path returned")

    bad = h({"scene": 9, "x": 0, "y": 0, "width": 1, "height": 1})
    assert bad.is_error and "no scene 9" in str(bad.content)
    tiny = h({"scene": 7, "x": 0, "y": 0, "width": 0.01, "height": 0.01})
    assert tiny.is_error
    print("unknown scene and useless box are errors")

    none = NT.NotesToolContext(refs_dir=d)
    assert "crop_still" not in {t["name"] for t in NT.build_tools(none)}
    print("no scenes, no crop tool")
```

- [ ] **Step 2: Run it to see it fail**

Run: `python isa_notes/tests/test_crop.py`
Expected: `AssertionError` at `"crop_still" in names`.

- [ ] **Step 3: Add the tool spec in `build_tools`**

In `isa_notes/notes_tools.py`, `build_tools` appends the diagram tools in two consecutive gated blocks near its end: `if ctx.boards and ctx.diagrams_dir is not None:` (the `crop_board` spec) followed by `if ctx.diagrams_dir is not None:` (the `check_diagram` spec, which is the long one with a nested `"name"` property). Delete both blocks and put this single block in their place, just before `return tools`:

```python
    if ctx.boards and ctx.diagrams_dir is not None:
        tools.append({
            "name": "crop_still",
            "description": (
                "Cut a region out of a screen still at native resolution, "
                "for embedding in the notes. Give the scene id from the "
                "scene index and a box as fractions of the whole image "
                "(x, y = top-left corner; width, height). Returns the "
                "relative path to put in ![](...) and shows you the crop. "
                "Use it for a GUI dialog, a menu, a chart, or a console "
                "error that the transcript cannot carry. Never crop a scene "
                "that shows a student's screen share."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "scene": {"type": "integer"},
                    "x": {"type": "number"}, "y": {"type": "number"},
                    "width": {"type": "number"}, "height": {"type": "number"},
                },
                "required": ["scene", "x", "y", "width", "height"],
            },
        })
```

Do the same in `build_handlers`: delete the `crop_board` and `check_diagram` nested functions, and in the registry replace

```python
    if ctx.diagrams_dir is not None:
        handlers["check_diagram"] = check_diagram
        if ctx.boards:
            handlers["crop_board"] = crop_board
```

with

```python
    if ctx.boards and ctx.diagrams_dir is not None:
        handlers["crop_still"] = crop_still
```

and add the handler next to `get_frame` (it reuses the existing `_image_result` helper):

```python
    def crop_still(inp: dict) -> ToolResult:
        from PIL import Image

        scene = next((s for s in ctx.boards
                      if str(s["id"]) == str(inp.get("scene"))), None)
        if scene is None:
            have = ", ".join(str(s["id"]) for s in ctx.boards) or "none"
            return ToolResult(f"Error: no scene {inp.get('scene')!r}. "
                              f"Available: {have}.", is_error=True)
        try:
            x, y, w, h = (float(inp[k]) for k in ("x", "y", "width", "height"))
        except (KeyError, TypeError, ValueError):
            return ToolResult("Error: x, y, width, height must be numbers "
                              "between 0 and 1.", is_error=True)
        if not (0 <= x < 1 and 0 <= y < 1 and 0.04 <= w <= 1 - x + 1e-9
                and 0.04 <= h <= 1 - y + 1e-9):
            return ToolResult(
                "Error: that box is off the image or smaller than 4% of it "
                "in one direction. Give x, y, width and height as fractions "
                "of the whole still.", is_error=True)
        root = Path(ctx.diagrams_dir)
        root.mkdir(parents=True, exist_ok=True)
        n = len(list(root.glob("crop-*.jpg"))) + 1
        dest = root / f"crop-{n:03d}.jpg"
        with Image.open(scene["path"]) as im:
            W, H = im.size
            box = (int(x * W), int(y * H), int((x + w) * W), int((y + h) * H))
            im.crop(box).save(dest, quality=90)
        emit(f"  [crop_still {scene['id']} {box}]")
        rel = f"{root.name}/{dest.name}"
        return _image_result(dest, (
            f"Scene {scene['id']} cropped to {box} (pixels). Embed it as "
            f"![describe what it shows]({rel}). If what you wanted is not in "
            f"frame, crop again with a different box."))
```

Delete the `from boards import zoom` and `from diagrams import ...` lazy imports that went with the removed functions. Then `grep -n "crop_board\|check_diagram\|from boards\|from diagrams" isa_notes/notes_tools.py isa_notes/claude_backend.py` must print nothing in `notes_tools.py`; in `claude_backend.py` the `board-locator` block inside `_run_subscription` (the `if ctx.boards and ctx.diagrams_dir is not None:` block that defines `agents["board-locator"]` and appends `DIAGRAM_INSTRUCTION`) must be deleted too, since its tool no longer exists. Leave `BOARD_LOCATOR_PROMPT` and `DIAGRAM_INSTRUCTION` constants in place if deleting them would break an import; otherwise delete them.

- [ ] **Step 4: Run all tests so far**

Run: `for t in isa_notes/tests/test_*.py; do python "$t" || echo "FAILED $t"; done`
Expected: no `FAILED` lines.

- [ ] **Step 5: Commit**

```bash
git add isa_notes
git commit -m "crop_still tool replaces the board crop and diagram check"
```

---

### Task 7: Prompts

**Files:**
- Create: `isa_notes/instructions.py`
- Create: `isa_notes/tests/test_instructions.py`

**Interfaces:**
- Produces: `instructions.SYSTEM_PROMPT: str`; `instructions.VERIFY_PROMPT: str`; `instructions.write_message(*, title, date, instructor, deck: Path | None, class_rmd: Path | None, transcript_text: str, scene_index: str, header: str) -> str`; `instructions.verify_message(*, notes: Path, instructor, deck, class_rmd, transcript_text, scene_index) -> str`.

- [ ] **Step 1: Write the failing test**

`isa_notes/tests/test_instructions.py`:

```python
"""What the model is told. The rules that matter most are the ones that
protect students and the ones that stop the notes from becoming a worse
copy of the slides; each is checked by a phrase that has to be present."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import instructions as I   # noqa: E402

for name, text in (("SYSTEM_PROMPT", I.SYSTEM_PROMPT), ("VERIFY_PROMPT", I.VERIFY_PROMPT)):
    assert "—" not in text, f"em dash in {name}"
    assert "\\todo" not in text and "LaTeX" not in text, name
    for phrase in ("a student asked", "screen share", "[hh:mm:ss]{.ts}",
                   "<!-- todo:", "Dr. Megahed"):
        assert phrase in text, f"{name} lacks {phrase!r}"
for phrase in ("restate a slide", "eval: false", "# <1>", "never invent output",
               "class RMD over the transcript", "speaker labels"):
    assert phrase.lower() in I.SYSTEM_PROMPT.lower(), phrase
print("both prompts carry the student-safety and fidelity rules")

msg = I.write_message(title="Class 03", date="2026-08-31",
                      instructor="Fadel Megahed", deck=Path("D.Rmd"),
                      class_rmd=None, transcript_text="[00:00:01] hi",
                      scene_index="**Screen stills** (0)", header="---\nx\n---\n")
assert "D.Rmd" in msg and "no in-class RMD" in msg.lower()
assert msg.index("---\nx\n---") < msg.index("[00:00:01] hi")
v = I.verify_message(notes=Path("notes.qmd"), instructor="Fadel Megahed",
                     deck=Path("D.Rmd"), class_rmd=Path("C.Rmd"),
                     transcript_text="[00:00:01] hi", scene_index="")
assert "notes.qmd" in v and "C.Rmd" in v
print("user messages name the sources and carry the transcript last")
```

- [ ] **Step 2: Run it to see it fail**

Run: `python isa_notes/tests/test_instructions.py`
Expected: `ModuleNotFoundError: No module named 'instructions'`

- [ ] **Step 3: Write `isa_notes/instructions.py`**

```python
"""instructions.py: what the note-writer and the checker are told.

The fidelity rules are the upstream notetaker's, reworded away from
mathematics: add nothing the instructor did not say, keep hedges, let a
correction supersede what it corrects, never let a todo license a false
statement. The rest is this course's: the class RMD wins over the transcript
for code, a still wins for anything clicked, students are anonymous, a
student's screen share is never embedded, and the notes may not restate the
slides.
"""

from __future__ import annotations

from pathlib import Path

ASR = """The transcript was produced by Zoom's automatic speech recognition and
contains errors: misheard words, mangled package and function names, and
nonsense where the instructor said something the recogniser could not handle.
Treat it as a rough guide, not a verbatim record. If a passage makes no sense
as R, as a tool's menu, or as English, it is probably a transcription error.
Use the clarify_transcript tool rather than reproducing garbled text."""

SPEAKERS = """Every transcript segment carries the instructor's name as its speaker,
because the room microphone attributes every voice to them. Speaker labels are
therefore useless for telling students from the instructor. Infer student
contributions from content instead: the instructor repeating a question back,
answering someone, addressing a person by name, or a sentence that only makes
sense as coming from the room. Write those as "a student asked" or "someone
pointed out". Never a name, never a quote long enough to identify a person,
and never a description of a student's own code."""

FIDELITY = """Fidelity. Notes like these fail in characteristic ways, and all of them come
from writing more than the class supports:
- Material you add that the instructor did not say (a justification, a
  tip, a "which is the same as", a best practice, an example) is where
  errors concentrate. Add it only where you are certain, and never present
  your own reasoning as the instructor's. If your own gloss genuinely helps,
  mark it as yours ("Editorially: ...").
- Preserve the instructor's confidence. "I think", "I am not sure", "this
  might have changed", "I forget" are content, not disfluency. Never turn a
  hedge into an assertion.
- A correction supersedes what it corrects. Instructors correct themselves,
  and students catch things, sometimes many minutes later. Write what the
  class concluded, not what was first said. When a passage sounds hesitant
  or draws a question, read ahead before writing it up.
- Never invent output values. If the console output, a number, a row
  count, or a chart was not shown on screen or in the class RMD, say what
  the code does, not what it printed.
- A todo does not license a false statement. Assert only the part you are
  sure of, and put the uncertainty inside the todo comment."""

SOURCES = """Sources, in order of authority when they disagree:
1. The in-class RMD, when there is one: what was actually typed. Prefer the
   class RMD over the transcript for every line of code, character for
   character. Reproduce its code chunks as fenced blocks with the r language
   tag and `#| eval: false` as the first line, so nothing runs when the page
   renders. Where the instructor walked through a chunk line by line, use
   Quarto code annotations: put `# <1>`, `# <2>` at the end of the lines
   being explained and a numbered list immediately below the block with one
   item per marker. Do not repeat the explanation in prose after the list.
2. Screen stills: what was on the shared screen. Prefer a still over the
   transcript for anything clicked in a GUI (Tableau, Power BI, Flourish,
   DataWrapper, RStudio menus). Embed a crop (crop_still) only where the
   transcript cannot carry the point: a dialog, a menu path, a chart the
   discussion turns on, a console error being diagnosed. R sessions with a
   class RMD usually need no stills at all.
3. The slide deck: the session's structure, learning objectives, and the
   code that was planned. Follow its parts as your section headings.
4. The transcript: what was said around all of the above."""

NOT_THE_SLIDES = """These notes are a companion to the slides, not a copy of them. Do not
restate a slide's bullets. Where a slide matters, name it ("Slide 14") and
write what the instructor said around it: the explanation, the example, the
story, the emphasis, the thing that was on the slide but got a different
spin out loud. A slide that passed without commentary gets no paragraph. In a
session with no code, the body is filled with the instructor's explanation
and examples in the same way; in a GUI lab, the notes read as a walkthrough
of what was clicked and why."""

SCREEN_SHARE = """Students sometimes share their screen for debugging. Zoom overlays the
sharer's name on the video, and the code is theirs. A still that shows a
student's screen share is never embedded and never cropped, and the notes
describe the debugging lesson in general terms ("a common error here is")
without the student's code, file names, or name. When a frame-reader report
says a frame is not the instructor's screen, treat it as off limits."""

TIMESTAMPS = """Mark where the material starts in the recording. Begin every paragraph
that came from the class with a timestamp span on the same line, before the
first word:

    [00:12:34]{.ts} The paragraph begins here.

Use exactly that form: [hh:mm:ss]{.ts}. The time is the [hh:mm:ss] on the
transcript line where the instructor STARTS that material, not where they
finish it, and never a time you estimated: copy the transcript's own mark.
Where a paragraph gathers a point made over several minutes, mark where the
point begins. Where you write something up out of the order it was said,
the mark follows the class, so times may go backwards; that is correct.
A paragraph with no spoken origin gets NO mark: a sentence joining two
topics, a summary of your own, background the instructor did not give. One
mark per paragraph: not per sentence, not on a heading, not inside a code
block, not on a list item (the paragraph introducing the list carries it)."""

READER = """Write for a reader who has these notes, the slides, the class RMD, and the
recording, and nothing else. The transcript and the stills are your working
materials, not the document's: the reader cannot open them and a still has
no number as far as they are concerned. So the prose may not point at them:
no "the transcript says", no "as seen in scene 41", no "the audio is unclear
here". Point at things the way the class does: "the dialog that opens", "the
code in the class RMD", "the chart on screen".
Two places are exempt because a reader never sees them:
- a todo comment, <!-- todo: ... -->, on its own line. Those are notes to
  the instructor, who does have the transcript and the stills, so name what
  you need looked at: <!-- todo: scene 41 unreadable, check the filter name -->
  is more use than a version that talks around it.
- the Loose ends section, written entirely as todo comments."""

VOICE = """Address the student as "you". Refer to the instructor as "Dr. Megahed" on
first mention and "Megahed" after, or write in the notes' own voice ("we
load the file"), which is what these notes mostly are. Clean up speech
disfluencies. Use en dashes or commas for asides; never an em dash. Keep
sentences short. Bold nothing except the first words of a list item where a
list has several parallel items."""

SHAPE = """The page, in order:
1. The front matter and header lines given in the task, verbatim, at the top.
2. "## What we covered": a short paragraph, then the session's learning
   objectives from the deck as a list.
3. Body sections following the deck's parts ("## Part 1: ..."), with
   "###" subsections as the material needs. Code from the class RMD in
   fenced r blocks with `#| eval: false`, annotated where walked through.
4. "## Questions from class": each student question paraphrased as "a
   student asked", with the answer given. Omit the section if there were
   none.
5. "## Loose ends": things the instructor said they would come back to, and
   anything you could not resolve, each as a todo comment on its own line.
   The heading stays even when the list is only comments; students then see
   an empty heading, which is acceptable."""

TOOLS = """Tools:
- Read: open the deck, the class RMD, and any still by its absolute path.
- Task with the frame-reader subagent: hand it timestamps and context to
  read frames cheaply; call get_frame yourself only when its report seems
  off and the passage matters.
- crop_still: a region of a scene still, at native resolution, for embedding.
- clarify_transcript: a garbled phrase, with your best guess.
- ask_user: a question the instructor should settle (what a mumbled function
  name was, whether a detour is worth keeping). Continue provisionally.
- get_user_answers: pick up answers before you finish.
Do not use web search or fetch for anything that could substitute for what
the class said. Looking up an R function's documentation to describe it
correctly is fine; importing a tutorial's explanation is not."""

SYSTEM_PROMPT = "\n\n".join([
    """You are writing companion notes for one session of ISA 401, an
undergraduate business analytics course at Miami University, from a Zoom
recording of the class. The notes are for the students who were in the room
and for those who missed it. They are Quarto Markdown, one page per session,
and they will be published next to the slides.""",
    ASR, SPEAKERS, FIDELITY, SOURCES, NOT_THE_SLIDES, SCREEN_SHARE,
    TIMESTAMPS, READER, VOICE, SHAPE, TOOLS,
    """The transcript provides timestamps [hh:mm:ss] before each segment and
scene markers where the screen changed. Use them to decide which stills to
open, to stamp any question you queue, and to write the timestamp spans."""])

VERIFY_PROMPT = "\n\n".join([
    """You are checking a set of companion notes for one ISA 401 class session
against the transcript, the class RMD, the slide deck, and the screen stills
they were written from. You did not write them; read them as a skeptical
student who has the recording to hand.

The question is not "does this read well?" It is "is each statement true,
and did the class actually support it?" Notes like these are usually right
about the main content and wrong in the material added around it.""",
    SPEAKERS, SCREEN_SHARE,
    """Look for exactly these, in order:

1. CODE THAT DIFFERS FROM THE CLASS RMD. Every fenced r block must match
   the class RMD character for character, apart from the `#| eval: false`
   line and the `# <n>` annotation markers. Fix the notes, never the RMD.
2. INVENTED OUTPUT. A number, a row count, a printed value, a chart
   description that was not shown on screen (check the still) or in the
   class RMD. Replace with what the code does.
3. RESTATED SLIDES. A paragraph that only repeats a slide's bullets. Delete
   it, or replace it with what was said around the slide if the transcript
   supports that.
4. UNSUPPORTED ADDITIONS. Tips, best practices, "which is the same as",
   examples, with no basis in the transcript. Delete or mark "Editorially:".
5. LOST HEDGES AND LOST CORRECTIONS. Places where the instructor hedged
   and the notes assert flatly; places where something was corrected later
   and the notes keep the first version.
6. STUDENTS. Any name, any quote long enough to identify a person, any
   description of a student's own code, any embedded image from a student's
   screen share. Remove it.
7. TIMESTAMPS. Every [hh:mm:ss]{.ts} must point at a transcript line that
   starts that material. A mark that is minutes off, or a mark on a
   paragraph the instructor never said, is wrong. Fix or remove.
8. GARBLE PROPAGATED. Transcription nonsense carried into the notes as if
   it were a function name or a term. Distinguish: the notes are wrong; the
   notes correctly repaired a garble (leave it); the notes carried it (fix).
9. PROSE THAT POINTS AT THE WORKING MATERIALS. "The transcript says", "scene
   41 shows", "the audio is unclear". Rewrite as what was actually said or
   shown, or move it into a todo comment.""",
    """Then fix what you found, editing the file in place:
- Fix anything you are confident is wrong with the smallest edit that makes
  it true. Do not restructure, do not rewrite prose you merely dislike.
- Where you suspect a problem but cannot settle it, weaken the claim and add
  <!-- todo: ... --> on its own line saying precisely what you doubt. Do not
  assert and flag.
- Preserve every [hh:mm:ss]{.ts} you do not have a reason to change. If you
  split a paragraph, mark the new one with the time its own material starts;
  if you merge two, keep the earlier mark.
- Preserve the front matter and the header lines at the top exactly.
- Refer to the instructor as "Dr. Megahed" on first mention and "Megahed"
  after; correct "the lecturer", "the professor", or a first name.

Finally, reply with a short report: one line per change made, one line per
doubt flagged. If the notes are clean, say so; do not invent work."""])


def _sources_block(deck: Path | None, class_rmd: Path | None) -> str:
    parts = []
    if deck:
        parts.append(f"**Slide deck** (xaringan R Markdown source): `{Path(deck).resolve()}`")
    else:
        parts.append("**Slide deck**: none on record for this session.")
    if class_rmd:
        parts.append(f"**Class RMD** (code typed live in class): `{Path(class_rmd).resolve()}`")
    else:
        parts.append("**Class RMD**: there is no in-class RMD for this session; "
                     "it was taught from the slides, a GUI tool, or discussion.")
    return "\n".join(parts)


def write_message(*, title: str, date: str | None, instructor: str,
                  deck: Path | None, class_rmd: Path | None,
                  transcript_text: str, scene_index: str, header: str) -> str:
    return (
        f"Write the companion notes for this class session.\n\n"
        f"**Session:** {title}" + (f" ({date})" if date else "") + "\n"
        f"**Instructor:** {instructor}. Refer to them as \"Dr. Megahed\" on "
        f"first mention and \"Megahed\" after.\n\n"
        f"{_sources_block(deck, class_rmd)}\n\n"
        f"Read the deck and the class RMD in full before you start writing.\n\n"
        f"**Front matter and header.** The file must begin with exactly this "
        f"text, then a blank line, then \"## What we covered\":\n\n"
        f"```\n{header}```\n\n"
        f"{scene_index}\n"
        f"**Transcript:**\n\n{transcript_text}"
    )


def verify_message(*, notes: Path, instructor: str, deck: Path | None,
                   class_rmd: Path | None, transcript_text: str,
                   scene_index: str) -> str:
    return (
        f"Check the notes in `{Path(notes).resolve()}`.\n\n"
        f"**Instructor:** {instructor}.\n\n"
        f"{_sources_block(deck, class_rmd)}\n\n"
        f"You may open any still by path, and the frame-reader subagent can "
        f"read frames at any timestamp.\n\n"
        f"{scene_index}\n"
        f"**Transcript:**\n\n{transcript_text}"
    )
```

- [ ] **Step 4: Run the test**

Run: `python isa_notes/tests/test_instructions.py`
Expected: two printed lines, exit 0.

- [ ] **Step 5: Commit**

```bash
git add isa_notes/instructions.py isa_notes/tests/test_instructions.py
git commit -m "Prompts for the ISA 401 note-writer and checker"
```

---

### Task 8: `session.py`: CLI, state, and stages

**Files:**
- Create: `isa_notes/session.py`
- Create: `isa_notes/tests/test_session.py`

**Interfaces:**
- Consumes: everything above. `claude_backend.run_agent(system_prompt=, user_text=, ctx=, output_file=, backend=, model=, frame_model=, revise=, wait_for_answers=, role=, log_dir=)`; `claude_backend.collect_followup_answers(ctx, output_file, segments)`, `claude_backend.count_todos`, `claude_backend.mark_answers_applied`; `notes_tools.NotesToolContext(refs_dir=, video_path=, total_duration=, transcript_path=, boards=, diagrams_dir=)`; `media.format_transcript`, `media.find_video`.
- Produces: `session.find_media(session_dir) -> tuple[Path, Path]` (mp4, vtt); `session.load_state(out) -> dict`; `session.save_state(out, state)`; `session.resolve_sources(session_dir, args, state) -> dict` with keys `instructor`, `video_url`, `video_url_template`, `deck`, `class_rmd`, `date`; `session.header_for(session_dir, sources) -> str`; `session.main(argv)`.

- [ ] **Step 1: Write the failing test**

`isa_notes/tests/test_session.py`:

```python
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
```

- [ ] **Step 2: Run it to see it fail**

Run: `python isa_notes/tests/test_session.py`
Expected: `ModuleNotFoundError: No module named 'session'`

- [ ] **Step 3: Write `isa_notes/session.py`**

```python
#!/usr/bin/env python3
"""session.py: one recorded ISA 401 class into one page of companion notes.

    python isa_notes/session.py sessions/class03 [--class-rmd F] [--deck F]
        [--instructor NAME] [--video-url URL] [--video-url-template T]
        [--answer] [--verify] [--no-verify] [--regen] [--publish DIR]
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
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import instructions as I                                   # noqa: E402
import qmd                                                 # noqa: E402
import scenes as SC                                        # noqa: E402
import vtt                                                 # noqa: E402
from claude_backend import (BACKENDS, collect_followup_answers,   # noqa: E402
                            count_todos, mark_answers_applied, run_agent)
from media import format_transcript                        # noqa: E402
from notes_tools import NotesToolContext                   # noqa: E402

PROJECT_ROOT = HERE.parent
SLIDES_URL = "https://fmegahed.github.io/isa401/fall2026/class{n:02d}/{stem}.html"
CLASS_CODE_URL = "https://github.com/fmegahed/isa401a/blob/main/markdowns/{name}"
TS_NOTE = ("Timestamps in the margin are hh:mm:ss into the recording; "
           "drag the player there to hear the passage.")
SAVED_KEYS = ("instructor", "video_url", "video_url_template", "deck",
              "class_rmd", "date")


# -- inputs ------------------------------------------------------------------

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


def resolve_sources(session_dir: Path, args, state: dict,
                    project_root: Path = PROJECT_ROOT) -> dict:
    n = qmd.class_number(session_dir)
    mp4, _ = find_media(session_dir) if list(Path(session_dir).glob("*.mp4")) \
        else (None, None)

    def pick(flag, key):
        return flag if flag not in (None, "") else state.get(key)

    deck = pick(args.deck, "deck")
    deck = Path(deck) if deck else qmd.find_deck(n, project_root / "isa401")
    rmd = pick(args.class_rmd, "class_rmd")
    rmd = Path(rmd) if rmd else qmd.find_class_rmd(n, project_root / "class_code")
    date = state.get("date") or (qmd.zoom_date(mp4.name) if mp4 else None)
    return {
        "instructor": pick(args.instructor, "instructor") or "Fadel Megahed",
        "video_url": pick(args.video_url, "video_url"),
        "video_url_template": pick(args.video_url_template, "video_url_template"),
        "deck": deck, "class_rmd": rmd, "date": date, "n": n,
    }


def header_for(src: dict) -> str:
    deck = src.get("deck")
    meta = qmd.deck_meta(deck) if deck and Path(deck).exists() else \
        {"title": f"ISA 401 Class {src['n']:02d}", "subtitle": ""}
    links = {
        "Slides": SLIDES_URL.format(n=src["n"], stem=Path(deck).stem) if deck else None,
        "Class code": CLASS_CODE_URL.format(name=Path(src["class_rmd"]).name)
        if src.get("class_rmd") else None,
        "Recording": src.get("video_url"),
    }
    return qmd.front_matter(meta["title"] or "ISA 401", meta["subtitle"],
                            src.get("date"), links, TS_NOTE)


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
        diagrams_dir=(out / "crops") if found else None)


def _transcript_text(tj: Path, found: list[dict]) -> str:
    return format_transcript(_segments(tj), SC.marks(found))


def stage_write(out: Path, mp4: Path, tj: Path, found: list[dict], src: dict,
                args) -> Path:
    notes = out / "notes.qmd"
    (out / "ts.css").write_bytes((HERE / "ts.css").read_bytes())
    header = header_for(src)
    meta = qmd.deck_meta(src["deck"]) if src.get("deck") else {"subtitle": ""}
    title = meta.get("subtitle") or f"Class {src['n']:02d}"
    user = I.write_message(
        title=title, date=src.get("date"), instructor=src["instructor"],
        deck=src.get("deck"), class_rmd=src.get("class_rmd"),
        transcript_text=_transcript_text(tj, found),
        scene_index=SC.index_text(found), header=header)
    print(f"  writing notes with the {args.backend} backend")
    run_agent(system_prompt=I.SYSTEM_PROMPT, user_text=user,
              ctx=_ctx(out, mp4, tj, found), output_file=notes,
              backend=args.backend, model=args.model,
              frame_model=args.frame_model, wait_for_answers=args.wait,
              role="write", log_dir=out / "logs")
    if qmd.ensure_front_matter(notes, header):
        print("  (front matter was missing; prepended)")
    return notes


def stage_verify(out: Path, mp4: Path, tj: Path, found: list[dict], src: dict,
                 args) -> None:
    notes = out / "notes.qmd"
    user = I.verify_message(
        notes=notes, instructor=src["instructor"], deck=src.get("deck"),
        class_rmd=src.get("class_rmd"),
        transcript_text=_transcript_text(tj, found),
        scene_index=SC.index_text(found))
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
        raise SystemExit(f"No notes at {notes}; write them first.")
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
        f"{I._sources_block(src.get('deck'), src.get('class_rmd'))}")
    run_agent(system_prompt=I.SYSTEM_PROMPT, user_text="\n\n".join(parts),
              ctx=ctx, output_file=notes, backend=args.backend,
              model=args.model, frame_model=args.frame_model, revise=True,
              wait_for_answers=args.wait, role="revise", log_dir=out / "logs")
    mark_answers_applied(ctx, notes)


def stage_render(out: Path, mp4: Path, tj: Path, found: list[dict], src: dict,
                 args) -> bool:
    notes = out / "notes.qmd"
    if src.get("video_url_template"):
        text = notes.read_text(encoding="utf-8")
        notes.write_text(qmd.link_timestamps(text, src["video_url_template"]),
                         encoding="utf-8")
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
    p.add_argument("--video-url", default=None)
    p.add_argument("--video-url-template", default=None,
                   help="e.g. https://youtu.be/ID?t={seconds}; turns timestamps into links")
    p.add_argument("--answer", action="store_true")
    p.add_argument("--verify", action="store_true", help="run only the checking pass")
    p.add_argument("--no-verify", dest="verify_after", action="store_false", default=True)
    p.add_argument("--regen", action="store_true")
    p.add_argument("--publish", metavar="DIR", default=None)
    p.add_argument("--no-scenes", dest="scenes", action="store_false", default=True)
    p.add_argument("--scene-threshold", type=float, default=0.30)
    p.add_argument("--wait", action="store_true")
    p.add_argument("--backend", default="subscription", choices=BACKENDS)
    p.add_argument("--model", default=None)
    p.add_argument("--frame-model", default=None)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
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
        copied = qmd.publish(notes, Path(args.publish))
        print(f"  published {len(copied)} file(s) to {args.publish}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test and the whole suite**

Run: `for t in isa_notes/tests/test_*.py; do python "$t" || echo "FAILED $t"; done`
Expected: no `FAILED` lines.

- [ ] **Step 5: Dry stages without a model**

Run: `python isa_notes/session.py sessions/class03 --no-verify --backend api`
This will reach the write stage and fail for lack of `ANTHROPIC_API_KEY`, which is the point: the transcript and scene stages must complete first. Expected output includes `transcript.json: N segments` and `scenes: N stills`, then a `SystemExit`/error mentioning the API key. Check `sessions/class03/out/scenes/` has between 30 and 400 JPEGs and that `scenes.json` intervals are monotone. If the count is above 400, the guard should have raised the threshold and said so. Leave `out/` in place; the real run reuses it.

- [ ] **Step 6: Commit**

```bash
git add isa_notes/session.py isa_notes/tests/test_session.py
git commit -m "session.py: CLI and stages for one class"
```

---

### Task 9: README, first real run, review

**Files:**
- Create: `isa_notes/README.md`

- [ ] **Step 1: Write `isa_notes/README.md`**

```markdown
# isa_notes

One recorded ISA 401 class in, one page of companion notes out.

## Setup, once

```sh
pip install -r isa_notes/requirements.txt   # claude-agent-sdk, anyio, pillow
claude                                       # log in with the Claude subscription
```

ffmpeg, ffprobe, and quarto must be on PATH. The course repos are cloned at
`isa401/` (decks) and `class_code/` (in-class RMDs); `git pull` in each after
class.

## Per class

1. Download the recording from Zoom cloud: the MP4, the audio transcript
   (`.transcript.vtt`), and optionally the M4A. Put them in
   `sessions/classNN/`.
2. Run:

   ```sh
   python isa_notes/session.py sessions/class03 --video-url https://miamioh.zoom.us/rec/share/...
   ```

   The deck and the class RMD are found by class number. Pass `--deck` or
   `--class-rmd` to override, `--instructor` if it is not Fadel Megahed.
   Flags are saved in `sessions/classNN/out/state.json` and need not be
   repeated.
3. Answer questions in the terminal as they appear, or press Enter to defer.
   Later: `python isa_notes/session.py sessions/class03 --answer`.
4. Open `sessions/class03/out/notes.html` and read it.
5. Publish: `--publish path/to/site/folder` copies `notes.qmd`, `ts.css`,
   and the stills the page embeds.

`--regen` rewrites the notes from scratch. `--verify` runs only the checking
pass. `--no-scenes` skips screen stills. `--no-verify` skips the checking
pass after writing.

## Tests

```sh
for t in isa_notes/tests/test_*.py; do python "$t" || echo "FAILED $t"; done
```

No test calls a model.
```

- [ ] **Step 2: Run the real thing on class 03**

Run: `python isa_notes/session.py sessions/class03`
This is a long agentic run on the subscription (expect 20 to 60 minutes including the verify pass). Watch for `[get_frame ...]`, `[crop_still ...]`, and `[Question #N ...]` lines. Answer or defer questions. At the end, expect `quarto render: ok`.

- [ ] **Step 3: Read the output**

Open `sessions/class03/out/notes.html` in a browser. Check, and write the answers down in the commit message of Step 5:
- front matter and header links present, timestamps styled muted and monospace;
- no student names anywhere (`grep -i` the qmd for names that appear in the transcript around "asked");
- every fenced r block matches `class_code/markdowns/03_r_basics.Rmd`;
- at most a handful of embedded images, none showing a name overlay other than the instructor's;
- timestamps spot-checked against the recording at three places.

- [ ] **Step 4: Run the suite once more**

Run: `for t in isa_notes/tests/test_*.py; do python "$t" || echo "FAILED $t"; done`
Expected: no `FAILED` lines.

- [ ] **Step 5: Commit**

```bash
git add isa_notes/README.md
git commit -m "isa_notes README; first end-to-end run on class 03"
```

---

## Self-review against the spec

- Sources and order of authority: Task 7 `SOURCES`.
- Zoom recording facts (speaker labels, student screen shares, no start-time URL): Task 7 `SPEAKERS` and `SCREEN_SHARE`; Task 5 `link_timestamps` with `--video-url-template` in Task 8.
- Layout `sessions/classNN/out/`: Task 8 `main`.
- Command and flags: Task 8 `parse_args`; `--deck` included.
- Stage 1 VTT merge with 1.5 s gap: Task 3 (plus a 30 s cap, added for timestamp precision).
- Stage 2 scenes, 0.30 threshold, 400 guard, spliced markers: Task 4.
- Stage 3 tools: `get_frame`/frame-reader (upstream, gated on `video_path`), `crop_still` (Task 6, replaces the spec's `crop_frame` name), question tools (upstream), Read/Write/Edit native. Removed tools: Task 1 and Task 6.
- Stage 4 verify checklist: Task 7 `VERIFY_PROMPT`.
- Stage 5 answer: Task 8 `stage_answer`.
- Stage 6 render check with one repair round, publish: Task 8 `stage_render`, Task 5 `publish`.
- Page shape, `eval: false`, annotations, timestamp span, todo comments, Loose ends: Task 7 `SHAPE`, `SOURCES`, `TIMESTAMPS`, `READER`. Deviation: chunks are fenced `r` blocks with `#| eval: false` under `engine: markdown`, so Quarto needs no R to render; same intent as the spec's `eval: false`.
- No-code sessions and "do not restate a slide": Task 7 `NOT_THE_SLIDES`.
- `ts.css`: Task 5.
- Tests listed in the spec: `test_vtt`, `test_scenes` (includes the splice check), `test_qmd`, `test_instructions`; plus `test_vendor`, `test_todo_syntax`, `test_crop`, `test_session`.
- Deferred items (Quarto Live, clips, site listing) are not in this plan by design.
