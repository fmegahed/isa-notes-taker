"""Zoom's audio_transcript.vtt: WEBVTT header, then numbered cues with
hh:mm:ss.mmm --> hh:mm:ss.mmm and one text line prefixed "Speaker Name: ".
Merging turns eight-second slivers into readable paragraphs without losing
the start time of the first cue, and stops at 30 s so a timestamp copied
from the transcript still lands within half a minute of the moment."""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import vtt   # noqa: E402

SAMPLE = """WEBVTT

1
00:00:02.900 --> 00:00:22.430
Fadel Megahed: Okay, so just as a reminder.

2
00:00:22.570 --> 00:00:30.360
Fadel Megahed: This week, we're gonna talk more about R.

3
00:00:35.000 --> 00:00:41.040
Fadel Megahed: After a gap.

4
00:00:41.100 --> 00:00:45.000
Guest: A different speaker.

5
00:00:45.100 --> 00:00:50.000
No colon here at all

6
00:01:00.000 --> 00:01:20.000
Fadel Megahed: Long one.

7
00:01:20.500 --> 00:01:40.000
Fadel Megahed: Would push the merged segment past 30 s.
"""

cues = vtt.parse_vtt(SAMPLE)
assert len(cues) == 7
assert cues[0]["start"] == 2.9 and cues[0]["end"] == 22.43
assert cues[0]["speaker"] == "Fadel Megahed"
assert cues[0]["text"] == "Okay, so just as a reminder."
assert cues[4]["speaker"] == "" and cues[4]["text"] == "No colon here at all"
print("cues parsed with times, speaker, text")

merged = vtt.merge_cues(cues)
# 1+2 merge (gap 0.14 s, same speaker); 3 stands alone (gap 4.6 s);
# 4 is another speaker; 5 has no speaker; 6 and 7 would exceed 30 s.
assert [m["start"] for m in merged] == [2.9, 35.0, 41.1, 45.1, 60.0, 80.5], \
    [m["start"] for m in merged]
assert merged[0]["end"] == 30.36
assert merged[0]["text"] == ("Okay, so just as a reminder. This week, we're "
                             "gonna talk more about R.")
print("merge joins close cues from one speaker, keeps the first start")

with tempfile.TemporaryDirectory() as d:
    src = Path(d) / "x.transcript.vtt"
    src.write_text(SAMPLE, encoding="utf-8")
    out = Path(d) / "transcript.json"
    n = vtt.write_transcript(src, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert n == 6 and len(data["segments"]) == 6
    assert data["metadata"]["cues"] == 7
    assert set(data["segments"][0]) == {"start", "end", "speaker", "text"}
print("transcript.json written in the upstream segment schema")

with tempfile.TemporaryDirectory() as d:
    src_bom = Path(d) / "bom.transcript.vtt"
    src_bom.write_bytes(b"\xef\xbb\xbf" + SAMPLE.encode("utf-8"))
    out_bom = Path(d) / "transcript.json"
    n_bom = vtt.write_transcript(src_bom, out_bom)
    data_bom = json.loads(out_bom.read_text(encoding="utf-8"))
    assert n_bom == n and len(data_bom["segments"]) == len(data["segments"])
    assert data_bom["segments"][0]["text"] == data["segments"][0]["text"]
print("a leading BOM parses to the same cue count")
