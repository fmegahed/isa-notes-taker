"""What the model is told. The rules that matter most are the ones that
protect students and the ones that stop the notes from becoming a worse
copy of the slides; each is checked by a phrase that has to be present."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import instructions as I   # noqa: E402

for name, text in (("SYSTEM_PROMPT", I.SYSTEM_PROMPT), ("VERIFY_PROMPT", I.VERIFY_PROMPT),
                   ("REFRAME_PROMPT", I.REFRAME_PROMPT)):
    assert "—" not in text, f"em dash in {name}"
    assert "\\todo" not in text and "LaTeX" not in text, name

for name, text in (("SYSTEM_PROMPT", I.SYSTEM_PROMPT), ("VERIFY_PROMPT", I.VERIFY_PROMPT)):
    for phrase in ("a student asked", "screen share", "[hh:mm:ss]{.ts}",
                   "<!-- todo:", "\"Fadel\""):
        assert phrase in text, f"{name} lacks {phrase!r}"
for phrase in ("restate a slide", "eval: false", "# <1>", "never invent output",
               "class RMD over the transcript", "speaker labels"):
    assert phrase.lower() in I.SYSTEM_PROMPT.lower(), phrase
for phrase in ("## Timeline", "Where students struggled", "For next time",
              "Suggestion:", "Open:"):
    assert phrase in I.SYSTEM_PROMPT, phrase
assert "What we covered" not in I.SYSTEM_PROMPT
assert "Address the student as" not in I.SYSTEM_PROMPT
# The instructor is "Fadel" in prose; pronouns are used, never printed as a label.
assert "never print pronouns" in I.SYSTEM_PROMPT
assert "Dr. Megahed\" on first mention" not in I.SYSTEM_PROMPT
assert "names what to check" in I.SYSTEM_PROMPT
print("both prompts carry the student-safety and fidelity rules")

assert "Keep every fenced r block" in I.REFRAME_PROMPT
assert "Open:" in I.REFRAME_PROMPT
print("REFRAME_PROMPT keeps code verbatim and lists open questions")

msg = I.write_message(title="Class 03", date="2026-08-31",
                      instructor="Fadel Megahed", deck=Path("D.Rmd"),
                      class_rmd=None, transcript_text="[00:00:01] hi",
                      scene_index="**Screen stills** (0)", header="---\nx\n---\n")
assert "D.Rmd" in msg and "no in-class rmd" in msg.lower()
assert msg.index("---\nx\n---") < msg.index("[00:00:01] hi")
assert "(he/him)" in msg and "call the instructor \"Fadel\"" in msg
assert "What we covered" not in msg
assert "Planned:" in msg
print("write_message's front-matter instruction names the Planned/Happened "
     "paragraphs, not the old 'What we covered' heading")
v = I.verify_message(notes=Path("notes.qmd"), instructor="Fadel Megahed",
                     deck=Path("D.Rmd"), class_rmd=Path("C.Rmd"),
                     transcript_text="[00:00:01] hi", scene_index="")
assert "notes.qmd" in v and "C.Rmd" in v
assert "(he/him)" in v
print("user messages name the sources and carry the transcript last")

r = I.reframe_message(notes=Path("notes.qmd"), instructor="Fadel Megahed",
                      deck=Path("D.Rmd"), class_rmd=None,
                      transcript_text="[00:00:01] hi", scene_index="",
                      header="---\nx\n---\n")
assert "notes.qmd" in r
assert r.index("---\nx\n---") < r.index("[00:00:01] hi")
print("reframe_message names the notes path and carries the header before the transcript")

msg_p = I.write_message(title="Class 03", date="2026-08-31",
                        instructor="Fadel Megahed", deck=Path("D.Rmd"),
                        class_rmd=None, transcript_text="[00:00:01] hi",
                        scene_index="**Screen stills** (0)", header="---\nx\n---\n",
                        pronouns="they/them")
assert "(they/them)" in msg_p and "(he/him)" not in msg_p
v_p = I.verify_message(notes=Path("notes.qmd"), instructor="Fadel Megahed",
                       deck=Path("D.Rmd"), class_rmd=Path("C.Rmd"),
                       transcript_text="[00:00:01] hi", scene_index="",
                       pronouns="they/them")
assert "(they/them)" in v_p and "(he/him)" not in v_p
print("instructor pronouns default to he/him and can be overridden in both messages")
