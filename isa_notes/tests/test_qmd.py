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
    notes = d / "notes.qmd"
    notes.write_text("# Body\n", encoding="utf-8")
    assert qmd.ensure_front_matter(notes, fm) is True
    assert notes.read_text(encoding="utf-8").startswith(fm)
    assert qmd.ensure_front_matter(notes, fm) is False
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
    (out / "notes.qmd").write_text(fm + "\n![](scenes/scene-041.jpg)\n", encoding="utf-8")
    (out / "ts.css").write_text(".ts{}")
    copied = qmd.publish(out / "notes.qmd", d / "site" / "class03")
    names = sorted(p.relative_to(d / "site" / "class03").as_posix() for p in copied)
    assert names == ["notes.qmd", "scenes/scene-041.jpg", "ts.css"], names
    print("publish copies the page, its css, and referenced images")

    ok, log = qmd.render(out / "notes.qmd")
    assert ok, log
    assert (out / "notes.html").exists()
    print("quarto render passes on a minimal page")
