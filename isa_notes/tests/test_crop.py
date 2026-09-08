"""A GUI step is worth a picture only if the picture shows the dialog and not
the whole desktop. crop_still cuts a fractional box out of a scene still at
native resolution and hands back a path the notes can embed."""
import sys
import tempfile
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import notes_tools as NT   # noqa: E402

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    still = d / "scenes" / "scene-007.jpg"
    still.parent.mkdir()
    Image.new("RGB", (400, 200), "white").save(still)
    ctx = NT.NotesToolContext(refs_dir=d, boards=[
        {"id": 7, "path": str(still), "start": 1.0, "end": 2.0}],
        diagrams_dir=d / "crops")
    names = {t["name"] for t in NT.build_tools(ctx)}
    assert "crop_still" in names and "crop_board" not in names
    assert "check_diagram" not in names
    h = NT.build_handlers(ctx)["crop_still"]

    r = h({"scene": 7, "x": 0.5, "y": 0.0, "width": 0.5, "height": 0.5})
    assert not r.is_error, r.content
    text = r.content[0]["text"] if isinstance(r.content, list) else r.content
    assert "crops/crop-001.jpg" in text, text
    im = Image.open(d / "crops" / "crop-001.jpg")
    assert im.size == (200, 100), im.size
    im.close()  # Windows can't rmtree an open file on TemporaryDirectory exit
    print("crop written at native resolution, path returned")

    bad = h({"scene": 9, "x": 0, "y": 0, "width": 1, "height": 1})
    assert bad.is_error and "no scene 9" in str(bad.content)
    tiny = h({"scene": 7, "x": 0, "y": 0, "width": 0.01, "height": 0.01})
    assert tiny.is_error
    print("unknown scene and useless box are errors")

    none = NT.NotesToolContext(refs_dir=d)
    assert "crop_still" not in {t["name"] for t in NT.build_tools(none)}
    print("no scenes, no crop tool")
