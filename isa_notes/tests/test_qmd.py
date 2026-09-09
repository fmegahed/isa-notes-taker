"""The Quarto side: where a session's deck and class code live, what goes in
the front matter, the two bits of syntax the model writes ([hh:mm:ss]{.ts}
and <!-- todo -->), and copying a finished page out."""
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import qmd   # noqa: E402

DECK = '''---
title: "ISA 401: Business Intelligence & Data Visualization"
subtitle: '03: `r paste0("<span>", fontawesome::fa("r-project"), "</span>")` Foundations'
author: 'x'
date: "Fall 2026"
output:
  xaringan::moon_reader:
    self_contained: true
---

# Slide
'''

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "sessions" / "class03").mkdir(parents=True)
    assert qmd.class_number(d / "sessions" / "class03") == 3
    deck_dir = d / "isa401" / "lectures" / "03_r_foundations"
    deck_dir.mkdir(parents=True)
    deck = deck_dir / "03_r_foundations.Rmd"
    deck.write_text(DECK, encoding="utf-8")
    assert qmd.find_deck(3, d / "isa401") == deck
    assert qmd.find_deck(9, d / "isa401") is None
    md = d / "class_code" / "markdowns"
    md.mkdir(parents=True)
    (md / "03_r_basics.Rmd").write_text("x")
    (md / "class04.Rmd").write_text("x")
    assert qmd.find_class_rmd(3, d / "class_code") == md / "03_r_basics.Rmd"
    assert qmd.find_class_rmd(4, d / "class_code") == md / "class04.Rmd"
    assert qmd.find_class_rmd(5, d / "class_code") is None
    print("deck and class RMD found by class number")

    meta = qmd.deck_meta(deck)
    assert meta["title"] == "ISA 401: Business Intelligence & Data Visualization"
    assert meta["subtitle"] == "03: Foundations", meta
    assert qmd.zoom_date("GMT20260831-123000_Recording_2426x1516.mp4") == "2026-08-31"
    assert qmd.zoom_date("nope.mp4") is None
    print("deck metadata and Zoom date parsed")

    fm = qmd.front_matter("T", "S", "2026-08-31",
                          {"Slides": "https://s", "Class code": None,
                           "Recording": "https://z"},
                          "Timestamps are hh:mm:ss into the recording.")
    assert fm.startswith("---\ntitle:") and "engine: markdown" in fm
    assert "css: ts.css" in fm and "[Slides](https://s)" in fm
    assert "Class code" not in fm, "links without a URL are dropped"
    assert "—" not in fm
    assert ("[Slides](https://s) | [Recording](https://z)\n\n"
           "Timestamps are hh:mm:ss into the recording.") in fm, fm
    assert "description" not in fm, "no description means no description line"

    fm_desc = qmd.front_matter("T", "S", "2026-08-31", {}, "",
                               description="We covered vectors and loops.")
    lines = fm_desc.splitlines()
    date_i = lines.index('date: "2026-08-31"')
    assert lines[date_i + 1] == 'description: "We covered vectors and loops."', fm_desc
    print("front_matter emits a quoted description line right after date")

    fm_nocss = qmd.front_matter("T", "S", "2026-08-31", {}, "", css=None)
    assert "css:" not in fm_nocss, fm_nocss
    assert "toc-depth: 3\n" in fm_nocss and "code-copy: true" in fm_nocss
    print("front_matter(css=None) omits the css line but keeps the rest")

    notes = d / "notes.qmd"
    notes.write_text("# Body\n", encoding="utf-8")
    assert qmd.ensure_front_matter(notes, fm) is True
    assert notes.read_text(encoding="utf-8").startswith(fm)
    assert qmd.ensure_front_matter(notes, fm) is False
    escaped_fm = qmd.front_matter('A \\ B "C"', "", None, {}, "")
    assert 'title: "A \\\\ B \\"C\\""' in escaped_fm, escaped_fm
    print("front matter assembled and prepended once")

    body = ("[00:12:34]{.ts} A paragraph.\n\n<!-- todo: check this @ 00:13:00 -->\n"
            "[01:02:03]{.ts} Another.\n![](scenes/scene-041.jpg)\n"
            "![alt](crops/crop-002.jpg){width=60%}\n")
    assert qmd.timestamps(body) == ["00:12:34", "01:02:03"]
    assert len(qmd.TODO_RE.findall(body)) == 1
    linked = qmd.link_timestamps(body, "https://youtu.be/ID?t={seconds}")
    assert "[[00:12:34](https://youtu.be/ID?t=754)]{.ts}" in linked, linked
    assert "[[01:02:03](https://youtu.be/ID?t=3723)]{.ts}" in linked
    assert qmd.referenced_images(body) == ["scenes/scene-041.jpg", "crops/crop-002.jpg"]
    print("timestamp and todo syntax; timestamp linking")

    out = d / "out"
    out.mkdir()
    (out / "scenes").mkdir()
    (out / "scenes" / "scene-041.jpg").write_bytes(b"x")
    body_with_image = fm + "\n![](scenes/scene-041.jpg)\n"
    (out / "notes.qmd").write_text(body_with_image, encoding="utf-8")
    (out / "ts.css").write_text(".ts{}")
    copied = qmd.copy_referenced_images(body_with_image, out, d / "site" / "class03")
    names = sorted(p.relative_to(d / "site" / "class03").as_posix() for p in copied)
    assert names == ["scenes/scene-041.jpg"], names
    assert (d / "site" / "class03" / "scenes" / "scene-041.jpg").exists()
    print("copy_referenced_images copies referenced images, preserving subpaths")

    out2 = d / "out2"
    out2.mkdir()
    (d / "outside.png").write_bytes(b"y")
    body_outside = fm + "\n![](../outside.png)\n"
    copied2 = qmd.copy_referenced_images(body_outside, out2, d / "site" / "class03b")
    assert not any(p.name == "outside.png" for p in copied2), copied2
    assert not (d / "site" / "outside.png").exists()
    print("copy_referenced_images refuses to follow a reference outside the notes folder")

    ok, log = qmd.render(out / "notes.qmd")
    assert ok, log
    assert (out / "notes.html").exists()
    print("quarto render passes on a minimal page")

    header2 = qmd.front_matter("T", "", None, {}, "")
    matching = header2 + "\n## Body\n"
    (d / "matching.qmd").write_text(matching, encoding="utf-8")
    assert qmd.front_matter_matches(d / "matching.qmd", header2) is True

    altered = header2.replace("engine: markdown", "engine: knitr")
    (d / "altered.qmd").write_text(altered + "\n## Body\n", encoding="utf-8")
    assert qmd.front_matter_matches(d / "altered.qmd", header2) is False

    (d / "nomatter.qmd").write_text("## Body only, no front matter\n",
                                    encoding="utf-8")
    assert qmd.front_matter_matches(d / "nomatter.qmd", header2) is False
    print("front_matter_matches catches a rewritten front matter block")

    exec_body = "prose\n\n```{r}\n1 + 1\n```\n\nmore prose\n"
    inert_body = "prose\n\n```r\n1 + 1\n```\n\nmore prose\n"
    assert qmd.executable_fences(exec_body) == ["```{r}"]
    assert qmd.executable_fences(inert_body) == []
    py_body = "```{python}\nprint(1)\n```\n"
    assert qmd.executable_fences(py_body) == ["```{python}"]
    print("executable_fences flags {r}/{python} cells but not inert r fences")

    mixed = ('![](scenes/scene-041.jpg)\n'
            '<img src="crops/crop-002.jpg" width="60%">\n'
            "<img src='crops/crop-003.jpg'>\n")
    assert qmd.referenced_images(mixed) == [
        "scenes/scene-041.jpg", "crops/crop-002.jpg", "crops/crop-003.jpg"], \
        qmd.referenced_images(mixed)
    print("referenced_images finds Markdown and <img> references, either quote style")

    # A real header (links line, then the recording/timestamp note that
    # front_matter always emits) must not be mistaken for the page's own
    # first paragraph.
    real_header = qmd.front_matter(
        "Class 03", "ISA 401", "2026-08-31",
        {"Slides": "https://s", "Class code": "https://c"},
        "The recording is on Canvas, available to ISA 401 instructors. "
        "Timestamps before each paragraph are hh:mm:ss into the recording.")
    assert "[Slides](https://s)" in real_header
    assert "The recording is on Canvas" in real_header

    planned_happened = (real_header + "Planned: cover vectors and loops.\n\n"
                        "Happened: We loaded a CSV, cleaned column names, and made a "
                        "scatterplot.\n\n## Timeline\n\nMore text.\n")
    assert qmd.page_summary(planned_happened) == (
        "We loaded a CSV, cleaned column names, and made a scatterplot.")

    long_sentence = "word " * 40
    happened_long = f"Happened: {long_sentence.strip()}.\n\n## Timeline\n"
    got = qmd.page_summary(happened_long)
    assert got is not None and len(got) <= 160, got
    assert not got.endswith(" "), "truncation lands on a word boundary"

    happened_ts = "Happened: [00:00:05]{.ts} We covered loops.\n\n## Timeline\n"
    assert qmd.page_summary(happened_ts) == "We covered loops.", \
        qmd.page_summary(happened_ts)

    # No "Happened:" paragraph: page_summary must skip the header's links
    # line and note paragraph and land on the real content paragraph, not
    # either piece of header boilerplate.
    no_happened = real_header + "This session covered vectors and loops.\n\n## Timeline\n"
    assert qmd.page_summary(no_happened) == "This session covered vectors and loops.", \
        qmd.page_summary(no_happened)

    # A content paragraph that happens to open with a Markdown link is not
    # the header's links line (which is nothing but links) and must be
    # returned, not swallowed as furniture, even as the very first
    # paragraph after the real header.
    link_paragraph = ("[Assignment](https://a) is due Friday. We covered arrays.")
    link_first = real_header + link_paragraph + "\n\n## Timeline\n"
    assert qmd.page_summary(link_first) == link_paragraph, qmd.page_summary(link_first)

    # A "Happened:" paragraph past the third one after the header is out of
    # scope; page_summary must not search the whole document for it.
    far_happened = (real_header
                    + "First.\n\nSecond.\n\nThird.\n\nHappened: too far to count.\n")
    assert qmd.page_summary(far_happened) == "First.", qmd.page_summary(far_happened)

    assert qmd.page_summary("## Timeline\n\n- only a list, no paragraph\n") is None
    print("page_summary prefers the Happened paragraph within the first three "
         "after the header, skips the header's links line and note, falls "
         "back to the first content paragraph, strips ts marks, and "
         "truncates at a word boundary")

    header_a = qmd.front_matter("Old title", "Old sub", "2026-08-31", {}, "")
    header_b = qmd.front_matter("New title", "New sub", "2026-08-31", {}, "",
                               description="New description.")
    original = header_a + "\n## Body\n\nSame content throughout.\n"
    replaced = qmd.replace_front_matter(original, header_b)
    assert qmd.front_matter_block(replaced) == qmd.front_matter_block(header_b)
    assert "## Body\n\nSame content throughout." in replaced
    assert "Old title" not in replaced and "Old sub" not in replaced
    print("replace_front_matter swaps the header, keeps the body")
