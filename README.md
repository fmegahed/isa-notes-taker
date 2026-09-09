# isa-notes-taker

Turns a recorded class session into a teaching note for whoever teaches ISA
401 next. Built for ISA 401 (Business Intelligence and Data Visualization) at
Miami University, where each class is recorded on Zoom, taught from xaringan
slides, and coded live in R Markdown. Started as student companion notes;
after faculty feedback it became a record for instructors, since students
learn more from taking their own notes.

This is an adaptation of [dmanam/notetaker](https://github.com/dmanam/notetaker)
by Deven Manam, a tool that turns recorded mathematics lectures into typeset
LaTeX notes. The agent runner, the asynchronous question queue, the
verification pass, the agent logging, and the media helpers come from that
project, vendored into `isa_notes/` and edited. Everything about mathematics,
LaTeX, chalkboards, diagrams, and bibliographies was removed; everything about
Zoom transcripts, screen stills, in-class code, and Quarto output is new. The
upstream state this was taken from is commit `a990f21` of 2026-09-03. Both
projects are MIT licensed; see `LICENSE`.

## What it does

For one class session, given Zoom's MP4 and transcript, the slide deck, and the
R Markdown file typed in class:

1. parses Zoom's VTT into a timestamped transcript;
2. pulls one still per change of the shared screen with ffmpeg;
3. has a Claude agent (on a Claude Code subscription) write `notes.qmd`: a
   teaching note for the next instructor, with a timeline of the session,
   where students struggled, demo notes and gotchas, the class code
   reproduced exactly with numbered annotations, timestamps into the
   recording before each paragraph, and student questions anonymized;
4. re-reads the page in a fresh context against the transcript and the code,
   and fixes what it can prove wrong;
5. queues questions for the instructor instead of guessing;
6. renders with Quarto, and publishes into a small website served from `docs/`.

## Where things are

| Path | What |
|---|---|
| `isa_notes/` | the tool; `isa_notes/README.md` explains how to run it |
| `notes_site/` | the Quarto website the published pages go into |
| `docs/` | the rendered site, served by GitHub Pages |
| `DEPLOY.md` | what gets copied where, and how the site reaches students |
| `planning/` | the design spec and the implementation plan |
| `sessions/` (not committed) | one folder per class with the Zoom download and the tool's output |

The course repositories it reads from,
[fmegahed/isa401](https://github.com/fmegahed/isa401) for the decks and
[fmegahed/isa401a](https://github.com/fmegahed/isa401a) for the in-class code,
are cloned locally alongside and are not part of this repository.

## Privacy

Recordings, transcripts, and audio never enter this repository. Published
pages embed at most a few cropped stills of the instructor's own screen.
Students are never named; a question from the room appears as "a student
asked". Stills of a student's screen share are never used.

## Requirements

Python 3.10 or newer, ffmpeg and ffprobe, Quarto 1.4 or newer, the Claude Code
CLI logged in with a Claude subscription, and the packages in
`isa_notes/requirements.txt`.
