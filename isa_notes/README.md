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
