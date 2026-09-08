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
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
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
        lines.append(" | ".join(items))
        if note:
            lines.append("")
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
    notes_root = notes.parent.resolve()
    for rel in ["notes.qmd", "ts.css"] + referenced_images(
            notes.read_text(encoding="utf-8")):
        if Path(rel).is_absolute() or not (notes.parent / rel).resolve().is_relative_to(notes_root):
            print(f"  (publish: {rel} points outside the notes folder; skipped)")
            continue
        src = notes.parent / rel
        if not src.exists():
            print(f"  (publish: {rel} is referenced but missing)")
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(target)
    return copied
