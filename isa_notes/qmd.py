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
_IMG_RE = re.compile(
    r"!\[[^\]]*\]\(([^)\s]+)\)"
    r"|<img\s[^>]*?src=[\"']([^\"']+)[\"']")
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
                 links: dict[str, str | None], note: str,
                 description: str | None = None,
                 css: str | None = "ts.css") -> str:
    def q(s: str) -> str:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    lines = ["---", f"title: {q(title)}"]
    if subtitle:
        lines.append(f"subtitle: {q(subtitle)}")
    if date:
        lines.append(f"date: {q(date)}")
    if description:
        lines.append(f"description: {q(description)}")
    lines += ["engine: markdown", "format:", "  html:", "    toc: true",
              "    toc-depth: 3"]
    if css:
        lines.append(f"    css: {css}")
    lines += ["    code-copy: true", "---", ""]
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


def front_matter_block(text: str) -> list[str] | None:
    """The file's leading `---` ... `---` block, as raw lines including both
    delimiters, or None if the text does not open with one."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[:i + 1]
    return None


_HEADING_RE = re.compile(r"^#{1,6}\s")


def _body_start(text: str) -> int:
    """The line index where the real page body begins: the first Markdown
    heading after the leading YAML front matter block, if any. A `header`
    (as `front_matter` builds it) is more than that YAML block -- it also
    has the links/note paragraph directly below it -- so swapping headers
    by line count of the YAML block alone would leave the old links line
    in place; anchoring on the first heading catches all of it."""
    lines = text.splitlines()
    block = front_matter_block(text)
    start = len(block) if block else 0
    for i in range(start, len(lines)):
        if _HEADING_RE.match(lines[i]):
            return i
    return len(lines)


def replace_front_matter(text: str, header: str) -> str:
    """Swap the file's whole header (front matter plus the links/note
    paragraph beneath it) for `header`, keeping the body -- from the
    first Markdown heading on -- untouched."""
    body = "\n".join(text.splitlines()[_body_start(text):])
    return header + "\n" + body if body else header


def front_matter_matches(path: Path, header: str) -> bool:
    """Whether the file's leading front matter block is still the one the
    header supplies, line for line, ignoring trailing whitespace. A model
    revising the file can rewrite or drop the front matter by mistake; this
    is how stage_render notices before handing a broken page to quarto."""
    file_block = front_matter_block(Path(path).read_text(encoding="utf-8"))
    header_block = front_matter_block(header)
    if file_block is None or header_block is None:
        return False
    return ([line.rstrip() for line in file_block]
           == [line.rstrip() for line in header_block])


_EXEC_FENCE_RE = re.compile(r"^```\{.*$", re.MULTILINE)


def executable_fences(text: str) -> list[str]:
    """Fenced code blocks the model wrote as executable (```` ```{r} ````,
    ```` ```{python} ````, ...) rather than inert (```` ```r ````). The page
    renders with `engine: markdown`, which does not execute code, but a
    model that reverts to the executable form would make quarto try to run
    it, and it should not run, ever."""
    return _EXEC_FENCE_RE.findall(text)


def timestamps(text: str) -> list[str]:
    return TS_RE.findall(text)


def link_timestamps(text: str, template: str) -> str:
    def sub(m: re.Match) -> str:
        secs = int(parse_timestamp(m.group(1)) or 0)
        return f"[[{m.group(1)}]({template.format(seconds=secs)})]{{.ts}}"
    return TS_RE.sub(sub, text)


_HAPPENED_RE = re.compile(r"^Happened:\s*", re.IGNORECASE)


def _clean_paragraph(lines: list[str]) -> str:
    return re.sub(r"\s+", " ", TS_RE.sub("", " ".join(lines))).strip()


def _truncate(para: str | None) -> str | None:
    if not para:
        return None
    if len(para) <= 160:
        return para
    return para[:160].rsplit(" ", 1)[0]


def _first_paragraph_after(text: str, start_line: int) -> str | None:
    """The first run of non-blank, non-heading, non-list lines starting
    at `start_line`, collapsed to one line. Used for the fallback branch
    of page_summary, where the page has no "Happened:" paragraph to key
    off, so the best guess is whatever paragraph opens the body."""
    lines: list[str] = []
    for line in text.splitlines()[start_line:]:
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if stripped.startswith(("#", "-", "*")) or re.match(r"^\d+[.)]", stripped):
            if lines:
                break
            continue
        lines.append(stripped)
    return _clean_paragraph(lines) if lines else None


def page_summary(text: str) -> str | None:
    """The listing description for a published page: the "Happened:"
    paragraph (the page's own account of what the session actually
    covered), stripped of its label; or, for a page that does not have
    one, the first paragraph after the front matter. Either way, collapsed
    to one line and truncated to 160 characters at a word boundary. None
    if there is nothing to summarize (a listing description is then just
    omitted, not left broken)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if _HAPPENED_RE.match(stripped):
            para_lines = [_HAPPENED_RE.sub("", stripped, count=1)]
            for follow in lines[i + 1:]:
                f_stripped = follow.strip()
                if not f_stripped:
                    break
                para_lines.append(f_stripped)
            return _truncate(_clean_paragraph(para_lines))
    block = front_matter_block(text)
    start = len(block) if block else 0
    return _truncate(_first_paragraph_after(text, start))


def referenced_images(text: str) -> list[str]:
    seen: list[str] = []
    for md_path, html_path in _IMG_RE.findall(text):
        p = md_path or html_path
        if p not in seen and not p.startswith(("http://", "https://")):
            seen.append(p)
    return seen


def render(path: Path) -> tuple[bool, str]:
    proc = subprocess.run(["quarto", "render", str(Path(path).name), "--to", "html"],
                          cwd=str(Path(path).parent), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    return proc.returncode == 0, (proc.stderr or "") + (proc.stdout or "")


def copy_referenced_images(text: str, src_root: Path, dest_root: Path) -> list[Path]:
    """Copy every image `text` references (Markdown or `<img>`) from
    `src_root` into `dest_root`, preserving relative subpaths. A reference
    that resolves outside `src_root` (or is absolute) is skipped rather
    than followed, the same guard the old `publish` used."""
    src_root = Path(src_root).resolve()
    copied: list[Path] = []
    for rel in referenced_images(text):
        if Path(rel).is_absolute() or not (src_root / rel).resolve().is_relative_to(src_root):
            print(f"  (publish: {rel} points outside the notes folder; skipped)")
            continue
        src = src_root / rel
        if not src.exists():
            print(f"  (publish: {rel} is referenced but missing)")
            continue
        target = Path(dest_root) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(target)
    return copied
