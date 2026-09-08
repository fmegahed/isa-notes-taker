"""Publishing a class's notes into notes_site/, rendering the whole site
into docs/, and the optional deploy-elsewhere and PDF steps. Uses a temp
project root (never the real notes_site/ or sessions/); calls the real
`quarto render`, so it is slower than the other tests."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import qmd            # noqa: E402
import session as S   # noqa: E402

REPO_NOTES_SITE = HERE.parent / "notes_site"


def make_session(root: Path, n: int, subtitle: str, covered: str,
                 image_rel: str | None = None) -> tuple[Path, dict]:
    out = root / "sessions" / f"class{n:02d}" / "out"
    out.mkdir(parents=True)
    deck_dir = root / "isa401" / "lectures" / f"{n:02d}_x"
    deck_dir.mkdir(parents=True)
    deck = deck_dir / f"{n:02d}_x.Rmd"
    deck.write_text(f'---\ntitle: "ISA 401"\nsubtitle: "{subtitle}"\n---\n',
                    encoding="utf-8")
    src = {"n": n, "deck": deck, "class_rmd": None, "date": "2026-08-31",
          "video_url": None, "instructor": "Fadel Megahed",
          "instructor_pronouns": None}
    header = S.header_for(src)
    body = f"## What we covered\n\n{covered}\n\n## Body\n\nSome prose.\n"
    if image_rel:
        img = out / image_rel
        img.parent.mkdir(parents=True, exist_ok=True)
        img.write_bytes(b"not a real image, just a placeholder")
        body += f"\n![]({image_rel})\n"
    (out / "notes.qmd").write_text(header + "\n" + body, encoding="utf-8")
    return out, src


with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    project_root = d / "project"
    notes_site = project_root / "notes_site"
    notes_site.mkdir(parents=True)
    for name in ("_quarto.yml", "index.qmd", "site.scss"):
        shutil.copy2(REPO_NOTES_SITE / name, notes_site / name)

    real_notes_site = S.NOTES_SITE
    real_project_root = S.PROJECT_ROOT
    real_docs_dir = S.DOCS_DIR
    S.NOTES_SITE = notes_site
    S.PROJECT_ROOT = project_root
    S.DOCS_DIR = project_root / "docs"
    try:
        # stage_deploy refuses before anything has been published (no docs/).
        no_docs_args = S.parse_args(["sessions/class03", "--deploy",
                                     str(d / "nowhere")])
        try:
            S.stage_deploy(no_docs_args)
            assert False, "stage_deploy must refuse without a docs/ folder"
        except SystemExit as e:
            assert "docs" in str(e)
        print("stage_deploy refuses before anything is published")

        out3, src3 = make_session(
            d, 3, "Foundations of R",
            "We covered vectors, data frames, and basic plotting in R.")
        out5, src5 = make_session(
            d, 5, "Data Wrangling",
            "We covered dplyr verbs for filtering, grouping, and summarizing.",
            image_rel="scenes/still.png")

        publish_args = S.parse_args(["sessions/class03", "--publish"])
        assert publish_args.pdf is False

        S.stage_publish(out3, src3, publish_args)
        S.stage_publish(out5, src5, publish_args)

        idx3 = notes_site / "class03" / "index.qmd"
        idx5 = notes_site / "class05" / "index.qmd"
        assert idx3.exists() and idx5.exists()
        t3 = idx3.read_text(encoding="utf-8")
        t5 = idx5.read_text(encoding="utf-8")
        assert 'title: "Foundations of R"' in t3, t3
        assert 'title: "Data Wrangling"' in t5, t5
        assert "description:" in t3 and "description:" in t5
        assert (notes_site / "class05" / "scenes" / "still.png").exists()
        print("stage_publish writes index.qmd with the subtitle as title, "
             "and a description")

        docs_index = S.DOCS_DIR / "index.html"
        assert docs_index.exists(), "stage_publish must render the whole site"
        html = docs_index.read_text(encoding="utf-8")
        assert "Foundations of R" in html and "Data Wrangling" in html
        print("the rendered site (docs/index.html) lists both sessions")

        assert (S.DOCS_DIR / ".nojekyll").exists()
        print("stage_publish leaves a .nojekyll marker in docs/")

        # -- deploy: file count, and an unrelated pre-existing file survives --
        deploy_dir = d / "deploy_target"
        deploy_dir.mkdir()
        unrelated = deploy_dir / "unrelated.txt"
        unrelated.write_text("keep me", encoding="utf-8")

        deploy_args = S.parse_args(["sessions/class03", "--deploy", str(deploy_dir)])
        S.stage_deploy(deploy_args)

        assert unrelated.exists() and unrelated.read_text(encoding="utf-8") == "keep me"
        docs_files = [p for p in S.DOCS_DIR.rglob("*") if p.is_file()]
        deployed_files = [p for p in deploy_dir.rglob("*")
                          if p.is_file() and p != unrelated]
        assert len(deployed_files) == len(docs_files), \
            (len(deployed_files), len(docs_files))
        print(f"stage_deploy copied {len(docs_files)} file(s) and left the "
             f"unrelated file alone")

        # -- deploy refuses a target inside the project ----------------------
        inside_args = S.parse_args(["sessions/class03", "--deploy",
                                    str(project_root / "somewhere")])
        try:
            S.stage_deploy(inside_args)
            assert False, "stage_deploy must refuse a target inside the project"
        except SystemExit as e:
            assert "inside this project" in str(e)
        print("stage_deploy refuses a target inside the project")

        # -- pdf: best effort; skip cleanly if typst is unavailable ----------
        out7, src7 = make_session(d, 7, "Time Series",
                                  "We covered ARIMA models for forecasting.")
        pdf_args = S.parse_args(["sessions/class07", "--publish", "--pdf"])
        S.stage_publish(out7, src7, pdf_args)
        pdf_path = S.DOCS_DIR / "class07" / "index.pdf"
        if pdf_path.exists():
            t7 = (notes_site / "class07" / "index.qmd").read_text(encoding="utf-8")
            assert "[PDF](index.pdf)" in t7, t7
            print("stage_publish rendered a PDF and linked it from the page")
        else:
            print("typst render unavailable, skipped")
    finally:
        S.NOTES_SITE = real_notes_site
        S.PROJECT_ROOT = real_project_root
        S.DOCS_DIR = real_docs_dir
