#!/usr/bin/env python3
"""Assign every testable requirement a test file and split them into work batches.

Writes tests/_batches/manifest.json and tests/_batches/bNNN.json.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import pad_section, test_basename, test_module

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQ_DIR = os.path.join(ROOT, "requirements")
TEST_DIR = os.path.join(ROOT, "tests")
BATCH_DIR = os.path.join(TEST_DIR, "_batches")
BATCH_SIZE = 40
MAX_BATCH_SIZE = 60


def one_line(text):
    return re.sub(r"\s+", " ", text).strip()


def section_key(section):
    key = []
    for part in section.split("."):
        m = re.fullmatch(r"(\d+)([a-z]*)", part)
        key.append((0, int(m.group(1)), m.group(2)) if m else (1, 0, part))
    return key


def main():
    entries = []
    for path in sorted(glob.glob(os.path.join(REQ_DIR, "[0-9A-D]*.json"))):
        chapter_file = os.path.splitext(os.path.basename(path))[0]
        data = json.load(open(path))
        sentences = {s["id"]: s for s in data["sentences"]}
        for req in data["requirements"]:
            if not req["testable"]:
                continue
            lines = [sentences[s]["lines"] for s in req["sentence_ids"] if s in sentences]
            examples = []
            for sid in req["examples"]:
                s = sentences.get(sid)
                if s:
                    examples.append({"lines": s["lines"], "text": s["text"][:1500]})
            entries.append({
                "id": req["id"],
                "section": req["section"],
                "chapter_dir": chapter_file,
                "type": req["type"],
                "modality": req["modality"],
                "original": one_line(req["original"]),
                "canonical": req["canonical"],
                "condition": req["condition"],
                "cross_refs": req["cross_refs"],
                "ambiguity": req["ambiguity"],
                "spec_lines": [min(l[0] for l in lines), max(l[1] for l in lines)] if lines else None,
                "examples": examples,
            })

    entries.sort(key=lambda e: section_key(e["section"]))
    counters = {}
    for e in entries:
        n = counters.get(e["section"], 0) + 1
        counters[e["section"]] = n
        base = test_basename(e["section"], n)
        e["file"] = f"tests/{e['chapter_dir']}/{base}.ttcn3"
        e["module"] = test_module(e["section"], n)
        e["header"] = f"// @requirement: {e['section']} -- {e['original']}"
        del e["chapter_dir"]

    # Group whole sections into batches of roughly BATCH_SIZE requirements.
    batches, current, last_section = [], [], None
    for e in entries:
        if current and len(current) >= BATCH_SIZE and e["section"] != last_section:
            batches.append(current)
            current = []
        if len(current) >= MAX_BATCH_SIZE:
            batches.append(current)
            current = []
        current.append(e)
        last_section = e["section"]
    if current:
        batches.append(current)

    os.makedirs(BATCH_DIR, exist_ok=True)
    manifest = []
    for i, batch in enumerate(batches, 1):
        name = f"b{i:03d}"
        with open(os.path.join(BATCH_DIR, name + ".json"), "w") as f:
            json.dump({"batch": name, "requirements": batch}, f, indent=1, ensure_ascii=False)
        manifest.append({
            "batch": name,
            "count": len(batch),
            "sections": sorted({e["section"] for e in batch}, key=section_key),
        })
        for e in batch:
            os.makedirs(os.path.join(ROOT, os.path.dirname(e["file"])), exist_ok=True)
    with open(os.path.join(BATCH_DIR, "manifest.json"), "w") as f:
        json.dump({"total": len(entries), "batches": manifest}, f, indent=1)
    print(f"{len(entries)} requirements in {len(batches)} batches", file=sys.stderr)


if __name__ == "__main__":
    main()
