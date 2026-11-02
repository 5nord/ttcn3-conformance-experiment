#!/usr/bin/env python3
"""Partition chapter sentence inventories into sub-agent sized parts.

Parts are cut at section boundaries. A part holds at most TARGET units unless
a single leaf section is larger. Writes sentences/parts/<part>.json and
sentences/parts.json (manifest).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENT = ROOT / "sentences"
TARGET = int(sys.argv[1]) if len(sys.argv) > 1 else 120


def depth(sec):
    return sec.count(".")


def groups(units, sections, prefix, level):
    """Return list of unit-lists, each a top-down section group under prefix."""
    order = [s for s in sections if s == prefix or s.startswith(prefix + ".")]
    children = [s for s in order if depth(s) == depth(prefix) + 1 and s.startswith(prefix + ".")]
    own = [u for u in units if u["section"] == prefix]
    result = []
    if own:
        result.append(own)
    for c in children:
        sub = [u for u in units if u["section"] == c or u["section"].startswith(c + ".")]
        if not sub:
            continue
        if len(sub) > TARGET and any(s.startswith(c + ".") for s in order):
            result.extend(groups(units, sections, c, level + 1))
        else:
            result.append(sub)
    return result


def main():
    manifest = json.loads((SENT / "chapters.json").read_text())
    (SENT / "parts").mkdir(exist_ok=True)
    for old in (SENT / "parts").glob("*.json"):
        old.unlink()
    parts = []
    for m in manifest:
        data = json.loads((SENT / f"{m['file']}.json").read_text())
        units = data["units"]
        if not units:
            continue
        gs = groups(units, list(data["sections"]), data["chapter"], 0)
        # Greedy packing of consecutive groups.
        packed, cur = [], []
        for g in gs:
            if cur and len(cur) + len(g) > TARGET:
                packed.append(cur)
                cur = []
            cur = cur + g
        if cur:
            packed.append(cur)
        assert sum(len(p) for p in packed) == len(units), m["file"]
        for i, p in enumerate(packed, start=1):
            pid = f"{m['file'].split('-')[0]}.part{i}" if len(packed) > 1 else m["file"].split("-")[0]
            secs = sorted({u["section"] for u in p}, key=lambda s: list(data["sections"]).index(s))
            part = {
                "part": pid,
                "chapter": data["chapter"],
                "chapter_file": m["file"],
                "title": data["title"],
                "sections": {s: data["sections"][s] for s in secs},
                "lines": [min(u["lines"][0] for u in p), max(u["lines"][1] for u in p)],
                "units": p,
            }
            (SENT / "parts" / f"{pid}.json").write_text(json.dumps(part, indent=1, ensure_ascii=False) + "\n")
            parts.append({"part": pid, "chapter": data["chapter"], "chapter_file": m["file"],
                          "first": secs[0], "last": secs[-1], "units": len(p), "lines": part["lines"]})
    (SENT / "parts.json").write_text(json.dumps(parts, indent=1) + "\n")
    for p in parts:
        print(f"{p['part']:12s} {p['units']:4d}  {p['first']} .. {p['last']}  lines {p['lines'][0]}-{p['lines'][1]}")
    print(len(parts), "parts")


if __name__ == "__main__":
    main()
