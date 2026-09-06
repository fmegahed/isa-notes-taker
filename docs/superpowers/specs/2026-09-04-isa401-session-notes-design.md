# ISA 401 session notes: design

Date: 2026-09-04
Status: approved in conversation, pending written review

## Purpose

Turn each recorded ISA 401 class session into one companion notes page for
students. The page narrates what was covered, keyed to the slide deck and to
the code written live in class, with timestamps into the Zoom recording so a
student can find the moment a point was made.

The tool is a new, small Python package that borrows the agent runner,
question queue, logging, and verification design from dmanam/notetaker (cloned
at `notetaker/`). Everything in that repo specific to mathematics lectures,
LaTeX, chalkboards, TikZ diagrams, and bibliographies is left behind.

## Sources per session

Three sources, in this order of authority when they disagree:

1. **Slide deck**: the xaringan `.Rmd` at `lectures/NN_topic/` in the
   course repo `fmegahed/isa401`, cloned locally. Gives structure, learning objectives,
   and the code planned for the session.
2. **In-class code**: the `.Rmd` committed live to the teaching repo
   `fmegahed/isa401a` under `markdowns/`. What was actually typed. Preferred
   over the transcript whenever the two disagree about code.
3. **Zoom recording**: an MP4 and Zoom's `audio_transcript.vtt`, downloaded
   by hand from Zoom cloud. What was said and what was on screen.

Some sessions (Tableau, Power BI, Flourish, DataWrapper labs) have no class
RMD. Those sessions rely on the deck, the transcript, and screen stills.

## Recording facts that shape the design

- Zoom records the room microphone. Every segment in the VTT carries the
  instructor's speaker label, including student questions picked up by the
  mic. Speaker labels therefore cannot be used to separate students from the
  instructor. The agent infers student contributions from content: the
  instructor repeating a question, answering someone, or a voice that is not
  the instructor's.
- Students sometimes share their screen for debugging. Zoom overlays the
  sharer's name on the video, and the code is the student's. Stills from a
  student screen share are never embedded in the notes, and the debugging
  lesson is written up without identifying code or names.
- Zoom cloud playback has no start-time URL parameter (Zoom developer forum
  thread 125904; Zoom community thread 243286). Timestamps are plain
  `hh:mm:ss` text. A `--video-url-template` flag exists for a host that does
  support start times (YouTube `?t=`, Kaltura `?st=`); when set, timestamps
  become links.

## Layout

The working folder `C:\Users\megahefm\Documents\claude\notetaker` is the
project. Both course repos are cloned inside it so the tool reads decks and
class code straight from git, and `git pull` in each after class is the
whole update step.

```
notetaker/            upstream dmanam/notetaker clone, read-only reference
isa401/               clone of fmegahed/isa401 (decks at lectures/NN_topic/NN_topic.Rmd)
class_code/           clone of fmegahed/isa401a (class code at markdowns/*.Rmd)
sessions/
  NN_topic/           one folder per class, named like the deck folder
    zoom/
      recording.mp4   Zoom download
      transcript.vtt  Zoom download
    transcript.json   everything below is written by the tool
    scenes/           scene-NNN.jpg + scenes.json
    notes.qmd
    notes.questions.json
    state.json        instructor name, video url, deck path, class rmd path
    logs/             one trace per agent run (agent_log.py)
isa_notes/            the tool
docs/superpowers/specs/   this document
```

Session media and outputs live under `sessions/`, outside both course
clones, so a Zoom recording can never be committed to a course repo by
accident. The three clones, `sessions/`, and all media are gitignored in
the project repo. The tool and the specs are committed.

The deck for a session is found by name: `sessions/03_r_foundations` reads
`isa401/lectures/03_r_foundations/03_r_foundations.Rmd`. `--deck PATH`
overrides that for a deck not yet pushed.

## Command

```
python -m isa_notes sessions/03_r_foundations \
    --class-rmd class_code/markdowns/03_r_basics.Rmd \
    --instructor "Fadel Megahed" \
    --video-url https://miamioh.zoom.us/rec/share/...
```

Flags saved to `state.json` on first use and not required again:
`--instructor`, `--video-url`, `--video-url-template`, `--class-rmd`, `--deck`.

Stage flags: `--answer` (follow-up on queued questions), `--verify`
(verification pass only), `--no-verify`, `--regen` (rewrite notes from
scratch), `--publish DIR`, `--no-scenes`, `--scene-threshold X`.

Backend flags pass through from the upstream repo: `--backend`
(`subscription` default), `--model`, `--frame-model`.

## Stages

Each stage is cached by the presence of its output. A rerun skips what
exists; `--regen` forces the notes stage.

### 1. VTT to transcript.json (`vtt.py`)

Parse Zoom's WebVTT: cue index, `hh:mm:ss.mmm --> hh:mm:ss.mmm`, then
`Speaker Name: text`. Output the upstream segment schema: a list of
`{"start": float, "end": float, "text": str, "speaker": str}`. The speaker
field is kept for completeness but the prompt is told it is unreliable.

Consecutive cues from the same speaker with a gap under 1.5 s are merged
into one segment so the transcript reads in paragraphs rather than
two-second slivers. Merging preserves the first cue's start time.

### 2. Scene stills (`scenes.py`)

ffmpeg only, no ML:

```
ffmpeg -i recording.mp4 -vf "scale=960:-2,select=gt(scene\,T),showinfo" -vsync vfr scenes/scene-%03d.jpg
```

with `T` defaulting to 0.30 and the `showinfo` log parsed for each still's
`pts_time`. A still's interval runs from its own time to the next still's
time. `scenes.json` records `{"id", "path", "start", "end"}`.

Guard against runaway counts: if more than 400 stills come out, the stage
reruns with a higher threshold and says so. Screen recordings with a
cursor moving over a static page do not trip a 0.30 threshold; typing in
RStudio does, roughly once per line, which is acceptable because the agent
gets an index, not 400 images in context.

The transcript given to the agent has a marker spliced in where each
scene starts, exactly as the upstream does with boards:

```
[00:23:12] === scene 41 up: sessions/03_r_foundations/scenes/scene-041.jpg ===
[00:23:14]  so if you look at the environment pane now ...
```

### 3. Notes (`instructions.py`, `__main__.py`)

The agent runs on the upstream `claude_backend.run_agent` with the
`subscription` backend. Tools available to it, from a trimmed copy of
`notes_tools.py`:

- `get_frame` and `analyze_frames` (Haiku reads stills on the main model's
  behalf; the main model looks itself only when a report seems off)
- `crop_frame` (native-resolution crop of a still, for embedding)
- `clarify_transcript`, `ask_user`, `get_user_answers` (the question broker)
- `read_file` restricted to the session folder, the deck, and the class RMD
- native Write/Edit for `notes.qmd`

Removed from the upstream tool set: `add_to_preamble`, `check_diagram`,
`locate_diagram`, `crop_board`, `cite_reference`, `fetch_document`,
`search_document`, `view_pdf_page`, and the board machinery.

The user message carries: session title and date from the deck's YAML, the
deck source, the class RMD source, the transcript with scene markers, and
the scene index.

### 4. Verify

A fresh context re-reads `notes.qmd` against the transcript, the class RMD,
and the stills. It fixes what it is sure of with the smallest edit that
makes the text true, and weakens what it cannot settle. The checklist:
code in the notes matches the class RMD character for character; every
timestamp points at a transcript line that actually starts that material;
no output value appears that was not shown on screen or in the RMD; no
student is identifiable; no still comes from a student screen share; every
hedge and correction in the transcript survived.

### 5. Answer

Unchanged from upstream in behaviour: `--answer` re-asks open questions,
offers each remaining todo, has the agent revise in place, and marks
answers applied. State lives in `notes.questions.json`.

### 6. Render check and publish

After the notes and verify stages, `quarto render notes.qmd` runs once. On
failure the error is handed to the agent for one repair round, content
untouched. `--publish DIR` copies `notes.qmd` and the stills it references
into `DIR`. Wiring the page into the isa401 site's listing is out of scope
for the first version.

## The notes page

`notes.qmd`, Quarto HTML, in this shape:

- **Header**: title and date; links to the slide deck, the class RMD on
  GitHub, and the Zoom recording; one line saying timestamps are
  `hh:mm:ss` into that recording.
- **What we covered**: a short paragraph and the deck's learning objectives.
- **Body**: sections following the deck's parts. Narrative of what was
  explained; the class RMD's code reproduced in chunks with `eval: false`;
  where the instructor walked through code line by line, Quarto code
  annotations (`# <1>` markers with a numbered list below the chunk) carry
  the explanation rather than prose after the chunk. Every paragraph that
  came from the recording begins with a timestamp span (`[hh:mm:ss]{.ts}`),
  styled muted inline. A paragraph the agent wrote itself carries none.
- **Sessions without code** (introduction, git, visualization fundamentals,
  GUI labs): the body has the same shape, filled with the instructor's
  explanation, examples, and emphasis rather than code. The notes may not
  restate a slide's bullets; they link to the slide by number and write
  what was said around it. A slide that passed without commentary gets no
  paragraph. In GUI labs the stills are the main evidence and the notes read
  as a walkthrough of what was clicked and why.
- **Screen stills**: embedded only where the transcript cannot carry the
  point (GUI menus and dialogs in Tableau, Power BI, Flourish, DataWrapper),
  cropped to the relevant region, never from a student screen share.
- **Questions from class**: student questions paraphrased as "a student
  asked", with the instructor's answer. No names.
- **Loose ends**: things the instructor said they would return to, and any
  unresolved todo, as HTML comments (`<!-- todo: ... -->`) so students do
  not see them.

The timestamp span and its CSS live in a small include (`ts.css`) that
`--publish` copies alongside the page.

## Prompt rules

Kept from upstream, reworded away from mathematics: the ASR caveat, the
fidelity block (add nothing the instructor did not say; keep hedges; a
correction supersedes what it corrects; a todo does not license a false
statement), the reader rule (the reader has the notes and the recording,
nothing else; never mention the transcript or the stills in prose), and the
timestamp rule.

Added:

- Prefer the class RMD over the transcript for code. Prefer a still over the
  transcript for anything clicked in a GUI.
- Never invent output values. If the output was not shown, say what the code
  does, not what it printed.
- Student contributions are inferred from content, never from speaker
  labels. Write them as "a student asked" or "someone pointed out". Never a
  name, never a quote long enough to identify a person.
- A still that shows a student's screen share is never embedded. Describe
  the debugging lesson in general terms.
- Address the student in second person. Refer to the instructor as
  "Dr. Megahed" on first mention and by surname after.
- No em dashes.

## Modules

New:

| File | Purpose |
|---|---|
| `isa_notes/__main__.py` | CLI, stage orchestration, state.json |
| `isa_notes/vtt.py` | Zoom VTT to transcript.json |
| `isa_notes/scenes.py` | ffmpeg scene stills and transcript splice |
| `isa_notes/instructions.py` | system prompt and verify checklist |
| `isa_notes/qmd.py` | timestamp span regex, todo comment regex, header assembly, render check |
| `isa_notes/ts.css` | timestamp styling |

Copied from upstream and trimmed: `claude_backend.py`, `notes_tools.py`,
`agent_log.py`, `media.py`, `usage.py`. Trimming means deleting the board,
diagram, preamble, bibliography, and document-fetch tools and their prompt
text, and changing the output-file instruction from LaTeX to Quarto.

## Testing

Plain assertion scripts under `isa_notes/tests/`, upstream style, no
framework, no model calls:

- `test_vtt.py`: a synthetic Zoom VTT with two speakers, overlapping cues,
  and a gap; checks segment times, merge behaviour, speaker retention.
- `test_scenes.py`: a 6 s video generated with ffmpeg `color` sources and
  three hard cuts; checks three stills, correct intervals, and the runaway
  guard on a threshold of 0.
- `test_splice.py`: scene markers land at the right transcript lines.
- `test_qmd.py`: timestamp and todo regexes; header assembly from a deck's
  YAML.
- `test_instructions.py`: the prompt contains every rule block and none of
  the removed LaTeX tool names.

## Cost

One session is a long agentic run on Opus under the Claude subscription,
plus a verify pass. Stills are read by Haiku. Expect a visible dent in plan
limits over a semester of roughly 28 sessions.

## Hosting

The notes are published to the isa401 GitHub Pages site. They are not
served from ChatISA (decided 2026-09-06).

## Deferred: live code with Quarto Live

Runnable R chunks in the browser are wanted, but not in the first version.
The plan, after one session's notes look right, is a spike on a single page:

- Quarto Live (`r-wasm/quarto-live`) for `{webr}` chunks.
- A client-side service worker that injects the COOP and COEP headers, since
  GitHub Pages cannot set response headers. Cross-origin isolation is what
  gives webR the SharedArrayBuffer channel it needs for any networking.
- A hidden setup chunk that sets `ALL_PROXY` to the public SOCKS5 over
  WebSocket proxy that ChatISA already uses, so chunks that read from a URL
  or scrape a page work without CORS.
- An audit of cross-origin subresources on the page (fonts, images), which
  `require-corp` blocks unless they send a resource policy header.

The spike has to confirm that Quarto Live's bundled webR selects the
SharedArrayBuffer channel once the page is isolated. If it passes, the tool
emits `{webr}` for self-contained chunks and keeps `eval: false` only where a
chunk needs something the browser cannot provide. If it fails, the notes stay
static and the decision is revisited.

Short video clips cut from the recording for GUI sequences are a possible
later addition to the scenes stage. Generic animation is not planned.

## Out of scope for the first version

Zoom API download, site listing integration, a course-wide assembled
document, practice questions, live code chunks (see above), and any use of
the NotebookLM material.
