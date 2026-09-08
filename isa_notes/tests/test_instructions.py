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
assert "gendered pronoun" in I.SYSTEM_PROMPT
assert "names what to check" in I.SYSTEM_PROMPT
print("both prompts carry the student-safety and fidelity rules")

msg = I.write_message(title="Class 03", date="2026-08-31",
                      instructor="Fadel Megahed", deck=Path("D.Rmd"),
                      class_rmd=None, transcript_text="[00:00:01] hi",
                      scene_index="**Screen stills** (0)", header="---\nx\n---\n")
assert "D.Rmd" in msg and "no in-class rmd" in msg.lower()
assert msg.index("---\nx\n---") < msg.index("[00:00:01] hi")
assert "No pronouns are on record" in msg
v = I.verify_message(notes=Path("notes.qmd"), instructor="Fadel Megahed",
                     deck=Path("D.Rmd"), class_rmd=Path("C.Rmd"),
                     transcript_text="[00:00:01] hi", scene_index="")
assert "notes.qmd" in v and "C.Rmd" in v
assert "No pronouns are on record" in v
print("user messages name the sources and carry the transcript last")

msg_p = I.write_message(title="Class 03", date="2026-08-31",
                        instructor="Fadel Megahed", deck=Path("D.Rmd"),
                        class_rmd=None, transcript_text="[00:00:01] hi",
                        scene_index="**Screen stills** (0)", header="---\nx\n---\n",
                        pronouns="he/him")
assert "(he/him)" in msg_p and "No pronouns are on record" not in msg_p
v_p = I.verify_message(notes=Path("notes.qmd"), instructor="Fadel Megahed",
                       deck=Path("D.Rmd"), class_rmd=Path("C.Rmd"),
                       transcript_text="[00:00:01] hi", scene_index="",
                       pronouns="he/him")
assert "(he/him)" in v_p and "No pronouns are on record" not in v_p
print("instructor pronouns, given or absent, are carried into both messages")
