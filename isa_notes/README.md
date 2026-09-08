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
   python isa_notes/session.py sessions/class03
   ```

   The deck and the class RMD are found by class number. Pass `--deck` or
   `--class-rmd` to override, `--instructor` if it is not Fadel Megahed.
   The page does not link the recording; its header says the recording is
   on Canvas. (`--video-url URL` would add a link instead.)
   Flags are saved in `sessions/classNN/out/state.json` and need not be
   repeated.
3. Answer questions in the terminal as they appear, or press Enter to defer.
   Later: `python isa_notes/session.py sessions/class03 --answer`. Pass
   `--wait` to block until every question the agent asks in this run has
   been answered, instead of leaving unanswered ones for a later
   `--answer` pass.
4. Open `sessions/class03/out/notes.html` and read it.
5. Publish: `--publish` lands the page in `notes_site/classNN/` and renders
   the whole notes website into `docs/`. Add `--pdf` for a downloadable
   PDF, `--deploy DIR` to also mirror `docs/` elsewhere. See `DEPLOY.md`
   at the project root for the full walkthrough, including the GitHub
   Pages setup.

`--regen` rewrites the notes from scratch. `--verify` runs only the checking
pass. `--no-scenes` skips screen stills. `--no-verify` skips the checking
pass after writing.

## Flags worth knowing about

- `--instructor-pronouns "they/them"`: the pronouns the prose uses for the
  instructor; the default is he/him. The notes call the instructor "Fadel"
  and never print pronouns as a label. Saved in `state.json` once passed, so
  it need not be repeated on later runs.
- `--video-url-template "https://youtu.be/ID?t={seconds}"`: turns every
  `[hh:mm:ss]{.ts}` timestamp in the notes into a link to that point in the
  recording, using `{seconds}` as the placeholder for the timestamp
  converted to seconds. Applied at render time, so it can be added on a
  later run without rewriting the notes.
- `--scene-threshold X` (default 0.30): the ffmpeg scene-change score above
  which a screen change gets its own still. Lower catches more, smaller
  changes; higher keeps only larger ones. Changing it on a session that
  already has `scenes/scenes.json` re-detects the stills instead of
  serving ones made at the old threshold.
- `--wait`: see step 3 above.

## Tests

```sh
for t in isa_notes/tests/test_*.py; do python "$t" || echo "FAILED $t"; done
```

PowerShell:

```powershell
Get-ChildItem isa_notes/tests/test_*.py | ForEach-Object { python $_.FullName; if ($LASTEXITCODE -ne 0) { "FAILED $($_.Name)" } }
```

No test calls a model.
