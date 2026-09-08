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
