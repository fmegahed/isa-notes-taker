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
